"""Normalizadores con enfoque Colombia: ciudades, modalidad, salarios en COP."""

from __future__ import annotations

import re

from app.domain.models import Modality, Seniority
from app.domain.skills import strip_accents

CITIES: dict[str, list[str]] = {
    "Bogotá": ["bogota", "bogota d.c.", "bogota dc", "bogota, d.c."],
    "Medellín": ["medellin", "valle de aburra"],
    "Cali": ["cali", "santiago de cali"],
    "Barranquilla": ["barranquilla"],
    "Cartagena": ["cartagena"],
    "Bucaramanga": ["bucaramanga"],
    "Pereira": ["pereira"],
    "Manizales": ["manizales"],
    "Envigado": ["envigado"],
    "Itagüí": ["itagui"],
    "Sabaneta": ["sabaneta"],
    "Bello": ["bello"],
    "Rionegro": ["rionegro"],
    "Cúcuta": ["cucuta"],
    "Santa Marta": ["santa marta"],
    "Ibagué": ["ibague"],
}
# Municipios del área metropolitana: se consideran compatibles entre sí
METRO_AREAS = {
    "Medellín": {"Medellín", "Envigado", "Itagüí", "Sabaneta", "Bello"},
}

_CITY_INDEX = {}
for canonical, syns in CITIES.items():
    _CITY_INDEX[strip_accents(canonical).lower()] = canonical
    for s in syns:
        _CITY_INDEX[s] = canonical


def normalize_city(raw: str | None) -> str | None:
    if not raw:
        return None
    key = strip_accents(raw).lower().strip()
    key = re.sub(r"\s*,?\s*(colombia|antioquia|cundinamarca|valle)$", "", key).strip()
    if key in _CITY_INDEX:
        return _CITY_INDEX[key]
    for syn, canonical in _CITY_INDEX.items():
        if re.search(r"\b" + re.escape(syn) + r"\b", key):
            return canonical
    return raw.strip().title()


def find_city_in_text(text: str) -> str | None:
    key = strip_accents(text).lower()
    for syn, canonical in sorted(_CITY_INDEX.items(), key=lambda kv: -len(kv[0])):
        if re.search(r"\b" + re.escape(syn) + r"\b", key):
            return canonical
    return None


def same_metro_area(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    return any(a in group and b in group for group in METRO_AREAS.values())


def normalize_modality(raw: str | None) -> Modality | None:
    if not raw:
        return None
    key = strip_accents(str(raw)).lower()
    if any(w in key for w in ("hibrid", "mixt", "semi presencial", "semipresencial")):
        return Modality.HIBRIDO
    if any(w in key for w in ("remot", "teletrabajo", "home office", "trabajo en casa", "virtual")):
        return Modality.REMOTO
    if any(w in key for w in ("presencial", "en sitio", "oficina", "on site", "onsite")):
        return Modality.PRESENCIAL
    return None


def normalize_seniority(raw: str | None) -> Seniority | None:
    if not raw:
        return None
    key = strip_accents(str(raw)).lower()
    if "practic" in key or "aprendiz" in key or "intern" in key:
        return Seniority.PRACTICANTE
    if "semi" in key or "mid" in key or "ssr" in key:
        return Seniority.SEMI_SENIOR
    if "senior" in key or "sr" == key.strip() or "lider" in key or "lead" in key:
        return Seniority.SENIOR
    if "junior" in key or "jr" in key or "trainee" in key:
        return Seniority.JUNIOR
    return None


def seniority_from_years(years: float | None) -> Seniority | None:
    if years is None:
        return None
    if years < 1:
        return Seniority.PRACTICANTE if years < 0.5 else Seniority.JUNIOR
    if years < 3:
        return Seniority.JUNIOR
    if years < 6:
        return Seniority.SEMI_SENIOR
    return Seniority.SENIOR


def parse_cop_amount(raw: str) -> int | None:
    """Convierte '4.500.000', '$4,5M', '4.5 millones', '3500000' a entero COP."""
    key = strip_accents(raw).lower().replace("cop", "").replace("$", "").strip()
    m = re.search(r"(\d+(?:[.,]\d+)*)\s*(m\b|mill|millones|mm)?", key)
    if not m:
        return None
    num, unit = m.group(1), m.group(2)
    if unit:
        n = num.replace(",", ".")
        if n.count(".") > 1:
            n = n.replace(".", "")
        return int(float(n) * 1_000_000)
    digits = re.sub(r"[.,]", "", num)
    if not digits:
        return None
    value = int(digits)
    if value < 100:  # "5" sin unidad: probablemente millones
        value *= 1_000_000
    elif value < 100_000:  # "4500" probablemente miles
        value *= 1_000
    return value


def parse_salary_range(raw: str | int | None) -> tuple[int | None, int | None]:
    """'$3.500.000 - $4.500.000', 'Hasta 6M', 'A convenir' -> (min, max)."""
    if raw is None:
        return None, None
    if isinstance(raw, int | float):
        return int(raw), int(raw)
    key = strip_accents(str(raw)).lower()
    if "convenir" in key or "negociable" in key:
        return None, None
    parts = re.split(r"\s+(?:-|a|y|hasta)\s+|\s*-\s*", key)
    amounts = [a for a in (parse_cop_amount(p) for p in parts if re.search(r"\d", p)) if a]
    if not amounts:
        return None, None
    if "hasta" in key and len(amounts) == 1:
        return None, amounts[0]
    if ("desde" in key or "mas de" in key) and len(amounts) == 1:
        return amounts[0], None
    return min(amounts), max(amounts)


def format_cop(value: int | None) -> str:
    if value is None:
        return "a convenir"
    return "$" + f"{value:,.0f}".replace(",", ".")


# ---------------------------------------------------------------- catálogos del perfil
CITY_DEPARTMENT = {
    "Bogotá": "Bogotá D.C.", "Medellín": "Antioquia", "Envigado": "Antioquia", "Itagüí": "Antioquia",
    "Sabaneta": "Antioquia", "Bello": "Antioquia", "Rionegro": "Antioquia", "Cali": "Valle del Cauca",
    "Barranquilla": "Atlántico", "Cartagena": "Bolívar", "Bucaramanga": "Santander", "Pereira": "Risaralda",
    "Manizales": "Caldas", "Cúcuta": "Norte de Santander", "Santa Marta": "Magdalena", "Ibagué": "Tolima",
}


def department_for(city: str | None) -> str | None:
    return CITY_DEPARTMENT.get(city or "")


DOCUMENT_TYPES = ["Cédula de ciudadanía", "Cédula de extranjería", "Pasaporte",
                  "Permiso por Protección Temporal (PPT)", "Tarjeta de identidad"]

# Sectores: los de Magneto vistos en el registro + sectores estándar del mercado colombiano
SECTORS = [
    "Administración y oficina", "Agropecuario", "Atención al cliente y call center", "Banca y seguros",
    "Comercio y ventas", "Comunicación y Periodismo", "Construcción e infraestructura",
    "Contabilidad, finanzas, impuestos y afines", "Deporte y recreación", "Diseño y artes gráficas",
    "Educación y docencia", "Hotelería, turismo y gastronomía", "Ingeniería", "Legal",
    "Logística, transporte y almacenamiento", "Manufactura y producción", "Mercadeo y publicidad",
    "Recursos humanos", "Salud", "Seguridad", "Servicios generales y mantenimiento",
    "Software, informática y telecomunicaciones",
]

WORKDAYS = ["Tiempo completo", "Medio tiempo", "Por horas", "Jornada diurna", "Jornada nocturna",
            "Fines de semana", "Temporada de fin de año", "Temporada de mitad de año", "Otras temporadas"]

CONTRACT_TYPES = ["Empleo (contrato laboral)", "Prestación de servicios", "Práctica / etapa productiva",
                  "Freelance / por proyecto"]

AVAILABILITY_OPTIONS = ["Inmediata", "15 días", "30 días", "Más de 30 días"]
SALARY_FREQUENCIES = ["mensual", "quincenal", "por hora", "por proyecto"]
SEX_OPTIONS = ["Hombre", "Mujer", "Intersexual", "Otro", "Prefiero no decir"]
DISABILITY_TYPES = ["Física", "Visual", "Auditiva", "Intelectual", "Psicosocial", "Múltiple", "Otra"]

_SECTOR_RULES = [
    (("desarroll", "software", "devops", "datos", "data", "qa", "ia ", "llm", "ux/ui", "sistemas", "soporte ti",
      "help desk", " bi "), "Software, informática y telecomunicaciones"),
    (("contab", "contador", "finanz", "tribut"), "Contabilidad, finanzas, impuestos y afines"),
    (("comercial", "ventas", "vendedor"), "Comercio y ventas"),
    (("marketing", "mercadeo", "community", "publicidad"), "Mercadeo y publicidad"),
    (("logist", "bodega", "inventario", "operaciones"), "Logística, transporte y almacenamiento"),
    (("diseñ", "grafic"), "Diseño y artes gráficas"),
    (("recursos humanos", "talento humano", "seleccion"), "Recursos humanos"),
]


def infer_sector(title: str) -> str | None:
    key = strip_accents(title).lower() + " "
    for words, sector in _SECTOR_RULES:
        if any(strip_accents(w) in key for w in words):
            return sector
    return None


def contract_category(raw: str | None) -> str:
    key = strip_accents(raw or "").lower()
    if "aprendiz" in key or "practic" in key or "etapa productiva" in key:
        return "Práctica / etapa productiva"
    if "prestacion" in key or "servicios" in key:
        return "Prestación de servicios"
    if "freelance" in key or "proyecto" in key or "obra" in key:
        return "Freelance / por proyecto"
    return "Empleo (contrato laboral)"


def smart_title(text: str) -> str:
    """'DESARROLLADOR DE SOFTWARE JUNIOR' -> 'Desarrollador de Software Junior'."""
    small = {"de", "del", "la", "las", "los", "y", "en", "e", "o", "a", "para", "con", "por"}
    words = text.lower().split()
    original = text.split()
    out = []
    for i, w in enumerate(words):
        if i and w in small:
            out.append(w)
        elif len(w) <= 2 and original[i].isupper():  # siglas: TI, IA, QA, UX
            out.append(original[i])
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


# ---------------------------------------------------------------- niveles educativos
EDUCATION_LEVELS = ["bachiller", "técnico", "tecnólogo", "profesional", "especialización", "maestría", "doctorado"]
_EDU_KEYS = {strip_accents(x): x for x in EDUCATION_LEVELS}


def normalize_education(raw: str | None) -> str | None:
    key = strip_accents(str(raw or "")).lower().strip()
    if key in ("tecnologo", "tecnologa"):
        return "tecnólogo"
    if key in ("tecnico", "tecnica"):
        return "técnico"
    return _EDU_KEYS.get(key) or next((v for k, v in _EDU_KEYS.items() if key.startswith(k[:6])), None)


def education_rank(level: str | None) -> int:
    lv = normalize_education(level)
    return EDUCATION_LEVELS.index(lv) if lv in EDUCATION_LEVELS else -1
