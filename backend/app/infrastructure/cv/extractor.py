"""Extracción de texto del CV (PDF o TXT) + parser por reglas.

Soporta dos estilos de CV:
  - Plantilla recomendada:  "Cargo | Empresa | Ciudad | Feb 2024 - Actual"
  - Fechas en la línea siguiente:  "Cargo — Empresa"  /  "Medellín | Enero 2024 – Octubre 2025"
Una hoja de vida NO trae expectativas: si aparece una sección así, se ignora.
"""

from __future__ import annotations

import io
import re

from app.domain.colombia import department_for, find_city_in_text, seniority_from_years, smart_title
from app.domain.languages import find_languages_in_text, parse_languages_text
from app.domain.models import Certification, Education, Experience, Profile, Project, Skill
from app.domain.skills import SKILL_CATALOG, extract_skills_from_text, in_catalog, split_level, strip_accents
from app.domain.skillset import make_skill, merge_skills

ALLOWED_EXTENSIONS = {".pdf", ".txt"}


class CVReadError(ValueError):
    pass


def extract_text(filename: str, content: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        if not content.startswith(b"%PDF"):
            raise CVReadError("El archivo no es un PDF válido")
        import pdfplumber

        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages[:10]]
        except Exception as exc:
            raise CVReadError("No se pudo leer el PDF") from exc
        text = "\n".join(pages)
    elif name.endswith(".txt"):
        text = content.decode("utf-8", errors="ignore")
    else:
        raise CVReadError("Formato no soportado. Usa PDF o TXT")
    text = re.sub(r"\(cid:\d+\)", "•", text.replace("\x00", "")).strip()
    if len(text) < 30:
        raise CVReadError("El CV no tiene texto legible (¿es una imagen escaneada?)")
    return text[:30_000]


# ---------------------------------------------------------------- patrones
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+?57[\s-]?)?3\d{2}[\s-]?\d{3}[\s-]?\d{4}")
PHONE_LABEL_RE = re.compile(r"(?:tel[eé]fono|celular|m[oó]vil|tel\.?|cel\.?)\s*:?\s*(\+?\d[\d\s-]{6,16}\d)", re.I)
DOC_RE = re.compile(r"\b(c\.?\s?c\.?|c\.?\s?e\.?|c[eé]dula(?: de ciudadan[ií]a| de extranjer[ií]a)?|pasaporte|ppt|"
                    r"documento)[:\s#No.]*([\d.]{6,13})", re.I)
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+/?", re.I)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w-]+(?:/[\w.-]+)?", re.I)
PORTFOLIO_RE = re.compile(r"(?:portafolio|portfolio|sitio web|web)\s*:\s*(\S+)", re.I)
URL_RE = re.compile(r"(?:https?://|www\.)\S+|(?:github|gitlab|behance)\.com/\S+", re.I)

_MONTHS = {"ene": 1, "jan": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4, "may": 5, "jun": 6, "jul": 7,
           "ago": 8, "aug": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12, "dec": 12}
_DATE = r"(?:[a-záéíóú]+\.?\s+(?:de\s+)?)?(?:19|20)\d{2}"
DATE_RANGE_RE = re.compile(rf"({_DATE})\s*(?:-|–|—|a|al|hasta)\s*({_DATE}|actual(?:mente)?|presente|present|hoy|now)",
                           re.I)
PLACEHOLDER_RE = re.compile(
    r"no especificad|no se especific|no se indica|no indicad|no proporcionad|pendiente|faltante|"
    r"sin informaci|por definir|por aclarar|no aplica|n/a\b|informaci[oó]n disponible|"
    r"documento ficticio|datos de contacto son", re.I)
NEGATION_RE = re.compile(r"\b(no se|no tengo|sin|ni)\b", re.I)
BULLET_RE = re.compile(r"^\s*[•\-*▪●◦·]\s*")
IN_PROGRESS_RE = re.compile(r"en curso|cursando|actualmente|en progreso|in progress|semestre", re.I)
SEMESTER_RE = re.compile(r"(\d{1,2})\s*\.?\s*[º°o]?\s*(?:er|do|ro|to|vo|no|mo)?\s*semestre", re.I)

SECTION_ALIASES = {
    "perfil": ["perfil", "perfil profesional", "resumen", "resumen profesional", "acerca de mi", "sobre mi",
               "summary", "profile", "about me"],
    "experiencia": ["experiencia", "experiencia laboral", "experiencia profesional", "historial laboral",
                    "trabajo", "trayectoria", "trayectoria laboral", "experience", "work experience"],
    "proyectos": ["proyectos", "proyectos academicos", "proyectos personales", "proyectos destacados",
                  "projects"],
    "educacion": ["educacion", "formacion", "formacion academica", "estudios", "educacion y formacion",
                  "education"],
    "certificaciones": ["cursos", "certificaciones", "cursos y certificaciones", "certificados",
                        "educacion complementaria", "educacion informal", "formacion complementaria",
                        "certifications", "courses"],
    "habilidades": ["habilidades", "skills", "competencias", "conocimientos", "habilidades tecnicas",
                    "tecnologias", "technical skills", "herramientas"],
    "idiomas": ["idiomas", "languages"],
    # Lo que NO es parte de una hoja de vida: se ignora (solo cierra la sección anterior)
    "_ignorar": ["expectativas", "expectativas laborales", "preferencias", "preferencias laborales",
                 "objetivo laboral", "referencias", "referencias personales", "referencias laborales",
                 "datos adicionales", "informacion adicional", "otros", "references", "datos personales"],
}
_HEADING_INDEX = {alias: key for key, aliases in SECTION_ALIASES.items() for alias in aliases}


def _clean(line: str) -> str:
    return strip_accents(line).lower().strip(" :•-*\t")


def _is_placeholder(text: str) -> bool:
    return bool(PLACEHOLDER_RE.search(text))


def _looks_like_heading(line: str) -> bool:
    """Línea corta en MAYÚSCULAS, sin dígitos ni comas: probablemente un encabezado no reconocido."""
    s = line.strip()
    return (s.isupper() and 1 <= len(s.split()) <= 5 and len(s) <= 40 and not re.search(r"[\d,@|]", s))


def split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"_header": []}
    current = "_header"
    seen_known = False
    for line in text.splitlines():
        if not line.strip():
            continue
        key = _HEADING_INDEX.get(_clean(line))
        if key:
            current, seen_known = key, True
            sections.setdefault(current, [])
            continue
        if seen_known and _looks_like_heading(line):
            current = "_otra"  # encabezado desconocido: no contamina la sección anterior
            continue
        sections.setdefault(current, []).append(line.strip())
    return sections


# ---------------------------------------------------------------- fechas
def _parse_date(raw: str) -> tuple[int, int] | None:
    raw_l = strip_accents(raw).lower()
    if re.search(r"actual|presente|present|hoy|now", raw_l):
        return None
    year = int(re.search(r"(19|20)\d{2}", raw_l).group(0))
    month = next((n for k, n in _MONTHS.items() if re.search(r"\b" + k, raw_l)), 1)
    return year, month


def _months_between(start: str, end: str | None, today: tuple[int, int] = (2026, 11)) -> int:
    s = _parse_date(start)
    e = _parse_date(end) if end else None
    e = e or today
    if not s:
        return 0
    return max((e[0] - s[0]) * 12 + (e[1] - s[1]) + 1, 1)


def years_of_experience(exps: list[Experience]) -> float | None:
    months = [_months_between(e.start, e.end) for e in exps if e.start]
    return round(sum(months) / 12, 1) if months else None


def _split_parts(head: str, split_en: bool = False) -> list[str]:
    pattern = r"\s+[|—–]\s+|\s+-\s+|\s+@\s+" + (r"|\s+en\s+(?=[A-ZÁÉÍÓÚ])" if split_en else "")
    parts = re.split(pattern, head)
    return [re.sub(r"\s*\([^)]*\)\s*$", "", p).strip(" |,-–—(:") for p in parts if p.strip(" |,-–—")]


_INSTITUTION_RE = re.compile(r"universidad|instituto|instituci|colegio|sena|corporaci|fundaci|escuela|academia", re.I)


def _is_city(part: str) -> bool:
    return bool(find_city_in_text(part)) and len(part.split()) <= 3 and not _INSTITUTION_RE.search(part)


def _no_paren(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", text).strip()


def _apply_meta_line(line: str, target: Experience | Education) -> None:
    """Línea tipo 'Medellín | Enero 2024 – Octubre 2025 | Graduado' que acompaña a un ítem."""
    m = DATE_RANGE_RE.search(line)
    for part in _split_parts(line):
        if _is_placeholder(part):
            continue
        if _is_city(part) and hasattr(target, "city") and not target.city:
            target.city = find_city_in_text(part)
    if isinstance(target, Experience) and m:
        target.start, target.end = m.group(1).strip(), m.group(2).strip()
        target.current = bool(re.search(r"actual|presente|present|hoy|now", m.group(2), re.I))
    if isinstance(target, Education):
        years = re.findall(r"(?:19|20)\d{2}", line)
        if years:
            target.year = years[-1]
        if IN_PROGRESS_RE.search(line):
            target.status = "en_curso"
            if sm := SEMESTER_RE.search(line):
                target.semester = int(sm.group(1))
        elif re.search(r"graduad|finalizad|terminad|titulad|completad", line, re.I) or years:
            target.status = target.status or "finalizado"


# ---------------------------------------------------------------- secciones
def _parse_experiences(lines: list[str]) -> list[Experience]:
    exps: list[Experience] = []
    current: Experience | None = None
    for i, line in enumerate(lines):
        is_bullet = bool(BULLET_RE.match(line))
        text = BULLET_RE.sub("", line).strip()
        m = DATE_RANGE_RE.search(text)
        if is_bullet:
            if current is not None and not _is_placeholder(text):
                current.description = ((current.description or "") + " " + text).strip()[:800]
            continue
        if m and (current is None or current.start or text[: m.start()].strip(" |,-–")):
            head = text[: m.start()].strip(" |,-–—(:")
            parts = [p for p in _split_parts(head, split_en=True) if not _is_placeholder(p)] if head else []
            if parts and current is not None and not current.start and _is_city(parts[0]) and len(parts) == 1:
                _apply_meta_line(text, current)  # "Medellín | 2023 – 2024" de la experiencia anterior
                continue
            if not parts and current is not None and not current.start:
                _apply_meta_line(text, current)
                continue
            city = next((p for p in parts[2:] if _is_city(p)), None)
            current = Experience(title=parts[0] if parts else "Cargo sin nombre",
                                 company=parts[1] if len(parts) > 1 and not _is_city(parts[1]) else None,
                                 city=find_city_in_text(city) if city else None)
            _apply_meta_line(text, current)
            exps.append(current)
            continue
        if m and current is not None:
            _apply_meta_line(text, current)
            continue
        if _is_placeholder(_no_paren(text)):
            if current is not None and "|" in text:
                _apply_meta_line(text, current)  # "Manizales | Periodo no especificado"
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        nxt_is_meta = bool(DATE_RANGE_RE.search(nxt) or BULLET_RE.match(nxt) or "|" in nxt)
        if (nxt_is_meta or re.search(r"\s[—|]\s", text)) and len(text.split()) <= 14:
            parts = [p for p in _split_parts(_no_paren(text), split_en=True) if not _is_placeholder(p)] or [text]
            current = Experience(title=parts[0], company=parts[1] if len(parts) > 1 else None)
            exps.append(current)
        elif current is not None:
            current.description = ((current.description or "") + " " + text).strip()[:800]
    return exps


EDU_LEVELS = [("doctor", "doctorado"), ("maestr", "maestría"), ("magister", "maestría"), ("master", "maestría"),
              ("especializ", "especialización"), ("tecnolog", "tecnólogo"), ("tecnic", "técnico"),
              ("ingenier", "profesional"), ("profesional", "profesional"), ("pregrado", "profesional"),
              ("licenci", "profesional"), ("administra", "profesional"), ("contadur", "profesional"),
              ("comunicacion", "profesional"), ("derecho", "profesional"), ("psicolog", "profesional"),
              ("engineer", "profesional"), ("bachelor", "profesional"), ("diplomad", "curso"),
              ("bootcamp", "curso"), ("curso", "curso"), ("bachiller", "bachiller")]
LEVEL_RANK = {"bachiller": 1, "técnico": 2, "tecnólogo": 3, "profesional": 4, "especialización": 5,
              "maestría": 6, "doctorado": 7}


def _parse_education(lines: list[str]) -> list[Education]:
    out: list[Education] = []
    current: Education | None = None
    for line in lines:
        text = BULLET_RE.sub("", line).strip()
        key = strip_accents(text).lower()
        level = next((lvl for k, lvl in EDU_LEVELS if k in key), None)
        has_year = bool(re.search(r"(?:19|20)\d{2}", text))
        is_meta = current is not None and (_is_city(_split_parts(text)[0] if _split_parts(text) else "")
                                           or (has_year and not level) or _is_placeholder(text)
                                           or re.search(r"graduad|finalizad|en curso|semestre", key))
        if is_meta and current is not None and not level:
            if not _is_placeholder(text):
                _apply_meta_line(text, current)
            continue
        if not level and not has_year and not re.search(r"\s[—|]\s|^estudios|^curso", key):
            continue
        parts = [p for p in _split_parts(_no_paren(text)) if not _is_placeholder(p)] or [text]
        degree = parts[0]
        institution = next((p for p in parts[1:] if not re.search(r"(?:19|20)\d{2}|en curso|semestre", p, re.I)
                            and not _is_city(p)), None)
        current = Education(degree=degree, institution=institution, level=level)
        _apply_meta_line(text, current)
        out.append(current)
    return out


def _parse_certifications(lines: list[str]) -> list[Certification]:
    out: list[Certification] = []
    for line in lines:
        text = BULLET_RE.sub("", line).strip()
        if _is_placeholder(text):
            continue
        if re.fullmatch(r"(?:19|20)\d{2}", text) and out:
            out[-1].year = text  # año en la línea siguiente
            continue
        parts = _split_parts(text)
        year = re.findall(r"(?:19|20)\d{2}", text)
        name = re.sub(r"\s*\b(?:19|20)\d{2}\b\s*", " ", parts[0]).strip()
        if name:
            out.append(Certification(name=name[:150], issuer=parts[1] if len(parts) > 1 and not
                                     re.fullmatch(r"(?:19|20)\d{2}", parts[1]) else None,
                                     year=year[-1] if year else None))
    return out[:15]


def _parse_projects(lines: list[str]) -> list[Project]:
    out: list[Project] = []
    for line in lines:
        is_bullet = bool(BULLET_RE.match(line))
        text = BULLET_RE.sub("", line).strip()
        if _is_placeholder(text):
            continue
        url = URL_RE.search(text)
        if is_bullet and out:
            out[-1].description = ((out[-1].description or "") + " " + text).strip()[:300]
            if url and not out[-1].url:
                out[-1].url = url.group(0).rstrip(".,")
            continue
        if url and out and not out[-1].url and len(text.split()) <= 3:
            out[-1].url = url.group(0).rstrip(".,")
            continue
        parts = _split_parts(text)
        out.append(Project(name=parts[0][:120], url=url.group(0).rstrip(".,") if url else None,
                           description=parts[1] if len(parts) > 1 and not re.fullmatch(r"(?:19|20)\d{2}", parts[1])
                           else None))
    for pr in out:
        pr.technologies = extract_skills_from_text(f"{pr.name} {pr.description or ''}")
        pr.evidence = "con_enlace" if pr.url else "descrito" if pr.description and pr.technologies else "declarado"
    return out[:10]


_CATALOG_KEYS = {k.lower() for k in SKILL_CATALOG} | {syn for _, syns in SKILL_CATALOG.values() for syn in syns}


def valid_skill(item: str, kind: str | None = None) -> Skill | None:
    """Valida un ítem listado como habilidad y captura su nivel ('Excel avanzado')."""
    s = item.strip(" .;:•-*\t")
    if not s or _is_placeholder(s) or NEGATION_RE.search(s):
        return None
    base, _level = split_level(s)
    if in_catalog(base):
        return make_skill(s, kind)
    if 1 < len(base) <= 40 and len(base.split()) <= 4 and not base.endswith(":"):
        return make_skill(s, kind)
    return None


def _parse_skills(lines: list[str]) -> list[Skill]:
    """Une líneas cortadas, ignora subtítulos ('Técnicas', 'Competencias') y valida cada ítem."""
    groups: list[list[str]] = [[]]
    for i, line in enumerate(lines):
        text = BULLET_RE.sub("", line).strip()
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        is_subtitle = ("," not in text and ";" not in text and len(text.split()) <= 4
                       and text[:1].isupper() and not text.endswith(".")
                       and ("," in nxt or ";" in nxt) and strip_accents(text).lower() not in _CATALOG_KEYS)
        if is_subtitle or _is_placeholder(text):
            groups.append([])
            continue
        groups[-1].append(text)
    items: list[Skill] = []
    for g in groups:
        joined = " ".join(g)
        for raw in re.split(r"[,;•|]|\s/\s|\.\s+(?=[A-ZÁÉÍÓÚ])", joined):
            parts = re.split(r"\s+y\s+", raw.strip(" ."))
            # "Comunicación y organización" = dos habilidades si ambas están en el catálogo
            pieces = parts if len(parts) == 2 and all(in_catalog(x) for x in parts) else [raw]
            for piece in pieces:
                ok = valid_skill(piece)
                if ok:
                    items.append(ok)
    return items


def _strip_negated(text: str) -> str:
    """Quita frases negadas ('no se especifican redes ni nivel de inglés') antes de buscar skills."""
    keep = []
    for sentence in re.split(r"(?<=[.\n])", text):
        if not NEGATION_RE.search(strip_accents(sentence)) and not _is_placeholder(sentence):
            keep.append(sentence)
    return " ".join(keep)


def split_full_name(full: str | None) -> tuple[str | None, str | None]:
    """Heurística colombiana: 4 palabras = 2 nombres + 2 apellidos; 3 = 1 + 2; 2 = 1 + 1."""
    if not full:
        return None, None
    w = full.split()
    if len(w) >= 4:
        return " ".join(w[:-2]), " ".join(w[-2:])
    if len(w) == 3:
        return w[0], " ".join(w[1:])
    if len(w) == 2:
        return w[0], w[1]
    return full, None


# ---------------------------------------------------------------- parser principal
def parse_cv_rules(text: str) -> Profile:
    """Parser determinista. Es el respaldo cuando no hay IA."""
    sec = split_sections(text)
    header = sec.get("_header", [])
    header_text = "\n".join(header)
    p = Profile()

    if m := EMAIL_RE.search(text):
        p.email = m.group(0).lower()
    if (m := PHONE_LABEL_RE.search(text)) or (m := PHONE_RE.search(text)):
        raw = m.group(1) if m.re is PHONE_LABEL_RE else m.group(0)
        p.phone = re.sub(r"[\s-]", "", raw)
    if m := DOC_RE.search(text):
        kind = strip_accents(m.group(1)).lower()
        p.document_id = m.group(2).replace(".", "")
        if "pasaporte" in kind:
            p.document_type = "Pasaporte"
        elif "ppt" in kind:
            p.document_type = "Permiso por Protección Temporal (PPT)"
        elif "extranjer" in kind or re.fullmatch(r"c\.?\s?e\.?", kind):
            p.document_type = "Cédula de extranjería"
        else:
            p.document_type = "Cédula de ciudadanía"
    if m := LINKEDIN_RE.search(text):
        p.linkedin = m.group(0)
    if m := GITHUB_RE.search(header_text):
        p.github = m.group(0)
    if (m := PORTFOLIO_RE.search(text)) and not _is_placeholder(m.group(1)):
        p.portfolio = m.group(1).rstrip(".,|")

    for line in header[:3]:
        generic = re.search(r"hoja de vida|curr[ií]cul|resume|\bcv\b", strip_accents(line).lower())
        if not generic and not EMAIL_RE.search(line) and not re.search(r"\d", line) and 2 <= len(line.split()) <= 6:
            p.full_name = smart_title(line) if line.isupper() else line
            break
    if p.full_name:
        idx = next((i for i, h in enumerate(header) if p.full_name.lower() in h.lower()), 0)
        nxt = header[idx + 1] if idx + 1 < len(header) else ""
        if nxt and not EMAIL_RE.search(nxt) and not PHONE_RE.search(nxt) and not find_city_in_text(nxt) \
                and not re.search(r"\d|@|linkedin|github", nxt, re.I):
            p.headline = (smart_title(nxt) if nxt.isupper() else nxt)[:150]
    p.first_names, p.last_names = split_full_name(p.full_name)
    p.city = find_city_in_text(header_text) or find_city_in_text(text[:1500])
    p.department = department_for(p.city)
    if sec.get("perfil"):
        p.summary = " ".join(x for x in sec["perfil"] if not _is_placeholder(x))[:800] or None

    p.experiences = _parse_experiences(sec.get("experiencia", []))
    p.projects = _parse_projects(sec.get("proyectos", []))
    p.education = _parse_education(sec.get("educacion", []))
    # Diplomados/cursos dentro de EDUCACIÓN se mueven a certificaciones
    p.certifications = _parse_certifications(sec.get("certificaciones", []))
    for e in [e for e in p.education if e.level == "curso"]:
        p.certifications.append(Certification(name=e.degree, issuer=e.institution, year=e.year))
        p.education.remove(e)
    p.years_experience = years_of_experience(p.experiences)
    p.seniority = seniority_from_years(p.years_experience)

    # En texto libre solo se buscan habilidades técnicas; las transversales cuentan si están en HABILIDADES
    clean_text = _strip_negated("\n".join(x for k, v in sec.items() if k not in ("_ignorar", "_otra") for x in v))
    p.skills = merge_skills(_parse_skills(sec.get("habilidades", [])), extract_skills_from_text(clean_text))
    if sec.get("idiomas"):
        p.languages = parse_languages_text("\n".join(sec["idiomas"]))
    else:
        p.languages = find_languages_in_text(clean_text)
    p.provenance = {f: "reglas" for f, v in p.model_dump().items()
                    if v not in (None, "", [], {}) and f not in ("country", "expectations", "sensitive",
                                                                 "first_job", "suggestions", "provenance",
                                                                 "edited_fields", "demonstrated_skills")}
    return p
