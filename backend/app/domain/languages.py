"""Idiomas: nombres, niveles (escala simple + MCER) y certificados.

Escala que ve el candidato: Básico / Intermedio / Avanzado / Nativo.
Internamente se conserva el MCER (A1..C2) para compararlo con lo que piden las vacantes ("Inglés B2").
"""

from __future__ import annotations

import re

from app.domain.models import Language, LanguageLevel
from app.domain.skills import strip_accents

LANGUAGE_NAMES = {
    "Español": ["espanol", "castellano", "spanish"],
    "Inglés": ["ingles", "english"],
    "Portugués": ["portugues", "portuguese"],
    "Francés": ["frances", "french"],
    "Alemán": ["aleman", "german"],
    "Italiano": ["italiano", "italian"],
    "Mandarín": ["mandarin", "chino", "chinese"],
    "Japonés": ["japones", "japanese"],
}
CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
CEFR_TO_LEVEL = {"A1": LanguageLevel.BASICO, "A2": LanguageLevel.BASICO, "B1": LanguageLevel.INTERMEDIO,
                 "B2": LanguageLevel.INTERMEDIO, "C1": LanguageLevel.AVANZADO, "C2": LanguageLevel.AVANZADO}
# Equivalencia mínima de cada nivel simple (para comparar con requisitos de vacantes)
LEVEL_TO_CEFR = {LanguageLevel.BASICO: "A2", LanguageLevel.INTERMEDIO: "B1", LanguageLevel.AVANZADO: "C1",
                 LanguageLevel.NATIVO: "C2"}
LEVEL_LABEL = {LanguageLevel.BASICO: "Básico (A1–A2)", LanguageLevel.INTERMEDIO: "Intermedio (B1–B2)",
               LanguageLevel.AVANZADO: "Avanzado (C1–C2)", LanguageLevel.NATIVO: "Nativo"}
# Escala que ve el candidato (MCER)
CEFR_OPTIONS = [
    {"value": "A1", "label": "A1", "hint": "Básico: frases muy sencillas"},
    {"value": "A2", "label": "A2", "hint": "Básico: temas cotidianos"},
    {"value": "B1", "label": "B1", "hint": "Intermedio: se defiende en el trabajo"},
    {"value": "B2", "label": "B2", "hint": "Intermedio alto: reuniones y correos con fluidez"},
    {"value": "C1", "label": "C1", "hint": "Avanzado: presentaciones y documentos complejos"},
    {"value": "C2", "label": "C2", "hint": "Dominio: como un nativo culto"},
    {"value": "nativo", "label": "Nativo", "hint": "Lengua materna"},
]

_WORD_LEVELS = [
    (("nativ", "lengua materna", "native", "mother tongue"), LanguageLevel.NATIVO),
    (("bilingue", "fluido", "fluent", "avanzado", "advanced", "proficient"), LanguageLevel.AVANZADO),
    (("intermedio", "intermediate", "conversacional"), LanguageLevel.INTERMEDIO),
    (("basico", "basic", "elemental", "principiante", "beginner"), LanguageLevel.BASICO),
]


def language_name(text: str) -> str | None:
    key = strip_accents(text).lower()
    for canonical, syns in LANGUAGE_NAMES.items():
        if any(re.search(r"\b" + s + r"\b", key) for s in syns):
            return canonical
    return None


def cefr_from_certificate(text: str) -> tuple[str | None, str | None]:
    """Convierte certificados conocidos a MCER. Devuelve (cefr, evidencia)."""
    key = strip_accents(text).lower()
    if m := re.search(r"ielts[^\d]{0,15}(\d(?:[.,]\d)?)", key):
        score = float(m.group(1).replace(",", "."))
        cefr = "C2" if score >= 8.5 else "C1" if score >= 7 else "B2" if score >= 5.5 else "B1" if score >= 4 else "A2"
        return cefr, f"IELTS {score:g}"
    if m := re.search(r"toefl[^\d]{0,15}(\d{2,3})", key):
        score = int(m.group(1))
        cefr = "C2" if score >= 114 else "C1" if score >= 95 else "B2" if score >= 72 else "B1" if score >= 42 else "A2"
        return cefr, f"TOEFL iBT {score}"
    for pattern, cefr, label in ((r"\b(cae|c1 advanced|cambridge advanced)\b", "C1", "Cambridge C1 Advanced"),
                                 (r"\b(cpe|c2 proficiency)\b", "C2", "Cambridge C2 Proficiency"),
                                 (r"\b(fce|b2 first|first certificate)\b", "B2", "Cambridge B2 First"),
                                 (r"\b(pet|b1 preliminary)\b", "B1", "Cambridge B1 Preliminary")):
        if re.search(pattern, key):
            return cefr, label
    if m := re.search(r"\b(dele|delf|dalf|celpe|goethe|ket|aptis)\b[^a-z]{0,5}([abc][12])\b", key):
        return m.group(2).upper(), f"{m.group(1).upper()} {m.group(2).upper()}"
    return None, None


def parse_language(text: str) -> Language | None:
    """'Inglés — B1 (intermedio)', 'English C1', 'Portugués', 'Inglés IELTS 7.0' -> Language."""
    name = language_name(text)
    if not name:
        return None
    key = strip_accents(text).lower()
    cefr, evidence = cefr_from_certificate(text)
    if not cefr and (m := re.search(r"\b([abc][12])\b", key)):
        cefr = m.group(1).upper()
    level = None
    if cefr:
        level = CEFR_TO_LEVEL[cefr]
    for words, lvl in _WORD_LEVELS:
        if any(w in key for w in words):
            level = lvl if lvl == LanguageLevel.NATIVO or level is None else level
            break
    if evidence:  # nivel deducido de un certificado: se muestra como sugerencia para confirmar
        return Language(name=name, level=level, cefr=cefr, suggested=True, evidence=f"Certificado {evidence}")
    if level and level != LanguageLevel.NATIVO and not cefr:
        # El CV dice "intermedio" pero no el nivel exacto: se propone uno y el candidato lo confirma
        return Language(name=name, cefr=LEVEL_TO_CEFR[level], suggested=True,
                        evidence=f"El CV dice '{level.value}' sin nivel exacto: confírmalo")
    return Language(name=name, level=level, cefr=cefr)


def parse_languages_text(text: str) -> list[Language]:
    """Separa 'Español — Nativo; Inglés — B1' o 'Español nativo, Inglés B2' en idiomas."""
    out: dict[str, Language] = {}
    for part in re.split(r"[;\n]|,(?![^()]*\))", text):
        lang = parse_language(part)
        if lang and (lang.name not in out or (out[lang.name].level is None and lang.level)):
            out[lang.name] = lang
    return list(out.values())


def find_languages_in_text(text: str) -> list[Language]:
    """Busca idiomas mencionados en texto libre ('hablo inglés a nivel B2')."""
    out: dict[str, Language] = {}
    for sentence in re.split(r"[.\n]", text):
        if re.search(r"\b(no|sin|ni)\b", strip_accents(sentence).lower()):
            continue  # "no se especifica nivel de inglés" no es un idioma que hable
        lang = parse_language(sentence)
        if lang and lang.name not in out:
            out[lang.name] = lang
    return list(out.values())


def cefr_rank(cefr: str | None) -> int:
    return CEFR_ORDER.index(cefr) if cefr in CEFR_ORDER else -1


def effective_cefr(lang: Language) -> str | None:
    if lang.cefr:
        return lang.cefr
    return LEVEL_TO_CEFR.get(lang.level) if lang.level else None


def suggest_spanish_native(langs: list[Language], cv_in_spanish: bool) -> list[Language]:
    """En un CV colombiano escrito en español, sugiere Español nativo (editable)."""
    out = [lang.model_copy() for lang in langs]
    es = next((lang for lang in out if lang.name == "Español"), None)
    if es is None and cv_in_spanish:
        out.insert(0, Language(name="Español", level=LanguageLevel.NATIVO, suggested=True,
                               evidence="CV escrito en español por un candidato en Colombia"))
    elif es is not None and es.level is None:
        es.level, es.suggested, es.evidence = LanguageLevel.NATIVO, True, "CV escrito en español"
    return out
