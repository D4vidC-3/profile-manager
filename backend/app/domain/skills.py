"""Catálogo de habilidades con tipo y sinónimos.

Tres tipos (siguiendo CUOC/DANE, ESCO y O*NET; los idiomas van aparte en `languages.py`):
  - herramienta:  herramientas y tecnologías (Excel, SAP, Python, Canva...)        -> admite nivel
  - conocimiento: conocimientos técnicos (Contabilidad, Estadística, Inventarios...) -> admite nivel
  - transversal:  habilidades blandas (Comunicación, Trabajo en equipo...)          -> sin nivel

Lo usan el Agente de Perfil y el de Vacantes para que "JS", "javascript" y "JavaScript" sean lo mismo.
"""

from __future__ import annotations

import re
import unicodedata

H, C, T = "herramienta", "conocimiento", "transversal"
KINDS = (H, C, T)
LEVELS = ("basico", "intermedio", "avanzado")

# nombre canónico -> (tipo, sinónimos en minúsculas y sin tildes)
SKILL_CATALOG: dict[str, tuple[str, list[str]]] = {
    # ------------------------------------------------ herramientas y tecnologías: programación y datos
    "Python": (H, ["python", "python3"]),
    "JavaScript": (H, ["javascript", "js", "ecmascript"]),
    "TypeScript": (H, ["typescript", "ts"]),
    "Java": (H, ["java"]),
    "C#": (H, ["c#", "csharp", "c sharp"]),
    ".NET": (H, [".net", "dotnet", "asp.net", ".net core"]),
    "Go": (H, ["golang"]),
    "PHP": (H, ["php"]),
    "Kotlin": (H, ["kotlin"]),
    "Swift": (H, ["swift"]),
    "R": (H, ["lenguaje r", "rstudio"]),
    "React": (H, ["react", "reactjs", "react.js"]),
    "Next.js": (H, ["next.js", "nextjs", "next"]),
    "Angular": (H, ["angular"]),
    "Vue": (H, ["vue", "vuejs", "vue.js"]),
    "Node.js": (H, ["node.js", "nodejs", "node"]),
    "Express": (H, ["express", "expressjs", "express.js"]),
    "Django": (H, ["django"]),
    "FastAPI": (H, ["fastapi"]),
    "Flask": (H, ["flask"]),
    "Spring Boot": (H, ["spring boot", "springboot", "spring"]),
    "HTML": (H, ["html", "html5"]),
    "CSS": (H, ["css", "css3"]),
    "Tailwind": (H, ["tailwind", "tailwindcss"]),
    "Android": (H, ["android"]),
    "SQL": (H, ["sql"]),
    "PostgreSQL": (H, ["postgresql", "postgres"]),
    "MySQL": (H, ["mysql"]),
    "SQL Server": (H, ["sql server", "mssql"]),
    "Oracle": (H, ["oracle", "pl/sql"]),
    "MongoDB": (H, ["mongodb", "mongo"]),
    "Neo4j": (H, ["neo4j"]),
    "Redis": (H, ["redis"]),
    "Pandas": (H, ["pandas"]),
    "NumPy": (H, ["numpy"]),
    "Apache Spark": (H, ["spark", "pyspark", "apache spark"]),
    "Airflow": (H, ["airflow", "apache airflow"]),
    "LangChain": (H, ["langchain", "langgraph"]),
    "Docker": (H, ["docker", "contenedores"]),
    "Kubernetes": (H, ["kubernetes", "k8s"]),
    "Terraform": (H, ["terraform"]),
    "AWS": (H, ["aws", "amazon web services"]),
    "Azure": (H, ["azure"]),
    "GCP": (H, ["gcp", "google cloud"]),
    "Git": (H, ["git", "github", "gitlab"]),
    "Linux": (H, ["linux", "ubuntu"]),
    "Windows": (H, ["windows", "windows server"]),
    "GraphQL": (H, ["graphql"]),
    "Selenium": (H, ["selenium"]),
    "Cypress": (H, ["cypress"]),
    "Postman": (H, ["postman"]),
    "VS Code": (H, ["vs code", "vscode", "visual studio code"]),
    "Jira": (H, ["jira"]),
    "Trello": (H, ["trello"]),
    # ------------------------------------------------ herramientas: ofimática, análisis y negocio
    "Excel": (H, ["excel", "microsoft excel", "hojas de calculo"]),
    "Tablas dinámicas": (H, ["tablas dinamicas", "pivot tables"]),
    "Google Sheets": (H, ["google sheets", "hojas de google"]),
    "Word": (H, ["microsoft word"]),
    "PowerPoint": (H, ["powerpoint", "power point"]),
    "Microsoft Office": (H, ["microsoft office", "office", "ofimatica", "paquete office"]),
    "Power BI": (H, ["power bi", "powerbi"]),
    "Power Query": (H, ["power query"]),
    "DAX": (H, ["dax"]),
    "Tableau": (H, ["tableau"]),
    "SAP": (H, ["sap"]),
    "ERP": (H, ["erp"]),
    "CRM": (H, ["crm"]),
    "Salesforce": (H, ["salesforce"]),
    "HubSpot": (H, ["hubspot"]),
    "World Office": (H, ["world office"]),
    "Siigo": (H, ["siigo"]),
    "Helisa": (H, ["helisa"]),
    "Google Analytics": (H, ["google analytics"]),
    "Google Ads": (H, ["google ads", "adwords"]),
    "Meta Ads": (H, ["meta ads", "facebook ads", "instagram ads"]),
    "WordPress": (H, ["wordpress"]),
    # ------------------------------------------------ herramientas: diseño e ingeniería
    "Figma": (H, ["figma"]),
    "Canva": (H, ["canva"]),
    "Adobe Photoshop": (H, ["photoshop", "adobe photoshop"]),
    "Adobe Illustrator": (H, ["illustrator", "adobe illustrator"]),
    "Adobe Premiere": (H, ["premiere", "adobe premiere"]),
    "AutoCAD": (H, ["autocad"]),
    "Revit": (H, ["revit"]),
    "SolidWorks": (H, ["solidworks"]),
    "Montacargas": (H, ["montacargas", "manejo de montacargas"]),
    # ------------------------------------------------ conocimientos técnicos: tecnología
    "REST APIs": (C, ["rest", "api rest", "apis rest", "restful", "rest api", "rest apis"]),
    "Microservicios": (C, ["microservicios", "microservices"]),
    "Pruebas unitarias": (C, ["pruebas unitarias", "unit testing", "pytest", "jest", "junit", "testing"]),
    "QA manual": (C, ["qa manual", "pruebas manuales", "pruebas funcionales"]),
    "CI/CD": (C, ["ci/cd", "cicd", "github actions", "jenkins", "integracion continua"]),
    "Scrum": (C, ["scrum", "metodologias agiles", "agil"]),
    "Kanban": (C, ["kanban"]),
    "Machine Learning": (C, ["machine learning", "aprendizaje automatico", "ml"]),
    "Inteligencia artificial": (C, ["inteligencia artificial", "ia generativa"]),
    "Análisis de datos": (C, ["analisis de datos", "data analysis"]),
    "Estadística": (C, ["estadistica", "statistics", "estadistica descriptiva"]),
    "Visualización de datos": (C, ["visualizacion de datos", "data visualization"]),
    "Limpieza de datos": (C, ["limpieza de datos", "data cleaning"]),
    "Bases de datos": (C, ["bases de datos", "modelado de datos"]),
    "Redes": (C, ["redes de computadores", "networking", "cableado estructurado"]),
    "Ciberseguridad": (C, ["ciberseguridad", "seguridad informatica", "cybersecurity"]),
    "Soporte técnico": (C, ["soporte tecnico", "mesa de ayuda", "help desk"]),
    "Mantenimiento de computadores": (C, ["mantenimiento de computadores", "mantenimiento basico de computadores",
                                          "mantenimiento de equipos de computo"]),
    "Instalación de software": (C, ["instalacion de software", "instalacion de programas"]),
    "UX/UI": (C, ["ux", "ui", "ux/ui", "diseno de experiencia", "experiencia de usuario"]),
    "Documentación técnica": (C, ["documentacion tecnica"]),
    # ------------------------------------------------ conocimientos: administración, finanzas y contabilidad
    "Contabilidad": (C, ["contabilidad", "contable"]),
    "NIIF": (C, ["niif", "ifrs"]),
    "Impuestos y tributaria": (C, ["tributaria", "impuestos", "declaraciones tributarias", "exogena"]),
    "Nómina": (C, ["nomina", "liquidacion de nomina"]),
    "Facturación electrónica": (C, ["facturacion electronica"]),
    "Conciliaciones bancarias": (C, ["conciliaciones bancarias", "conciliaciones"]),
    "Finanzas": (C, ["finanzas", "analisis financiero"]),
    "Presupuestos": (C, ["presupuestos", "presupuesto"]),
    "Costos": (C, ["costos", "contabilidad de costos"]),
    "Auditoría": (C, ["auditoria"]),
    "Cartera y cobranza": (C, ["cartera", "cobranza", "recaudo"]),
    "Gestión documental": (C, ["gestion documental", "archivo"]),
    "Gestión de proyectos": (C, ["gestion de proyectos", "project management", "pmp"]),
    "Gestión de calidad": (C, ["gestion de calidad", "iso 9001", "sistemas de gestion"]),
    # ------------------------------------------------ conocimientos: logística y operaciones
    "Control de inventarios": (C, ["control de inventarios", "inventarios", "conteos ciclicos"]),
    "Logística": (C, ["logistica", "logistica de distribucion"]),
    "Cadena de suministro": (C, ["cadena de suministro", "supply chain"]),
    "Compras": (C, ["compras", "abastecimiento"]),
    "Gestión de proveedores": (C, ["gestion de proveedores", "proveedores"]),
    "Almacenamiento y bodega": (C, ["almacenamiento", "bodega", "alistamiento", "picking"]),
    "Despachos": (C, ["despachos", "distribucion"]),
    "Indicadores KPI": (C, ["indicadores kpi", "kpi", "kpis", "indicadores"]),
    # ------------------------------------------------ conocimientos: comercial y mercadeo
    "Ventas": (C, ["ventas", "venta consultiva"]),
    "Marketing digital": (C, ["marketing digital", "mercadeo digital"]),
    "Redes sociales": (C, ["redes sociales", "social media", "instagram", "tiktok"]),
    "Creación de contenido": (C, ["creacion de contenido", "content creation", "copywriting"]),
    "SEO": (C, ["seo", "posicionamiento web"]),
    "Investigación de mercados": (C, ["investigacion de mercados"]),
    "Diseño gráfico": (C, ["diseno grafico"]),
    # ------------------------------------------------ conocimientos: talento humano, salud, legal y otros
    "Recursos humanos": (C, ["recursos humanos", "talento humano", "gestion humana"]),
    "Selección de personal": (C, ["seleccion de personal", "reclutamiento"]),
    "Seguridad y salud en el trabajo": (C, ["seguridad y salud en el trabajo", "sst", "sg-sst"]),
    "Derecho laboral": (C, ["derecho laboral", "legislacion laboral"]),
    "Primeros auxilios": (C, ["primeros auxilios"]),
    "Facturación en salud": (C, ["facturacion en salud", "rips", "glosas"]),
    "Atención de pacientes": (C, ["atencion de pacientes", "cuidado de pacientes"]),
    "Manipulación de alimentos": (C, ["manipulacion de alimentos"]),
    "Docencia": (C, ["docencia", "ensenanza", "pedagogia"]),
    "Electricidad": (C, ["electricidad", "instalaciones electricas"]),
    "Mecánica": (C, ["mecanica", "mantenimiento mecanico"]),
    "Construcción": (C, ["construccion", "obra civil"]),
    # ------------------------------------------------ transversales (blandas)
    "Comunicación": (T, ["comunicacion", "comunicacion asertiva", "comunicacion efectiva"]),
    "Trabajo en equipo": (T, ["trabajo en equipo", "trabajo colaborativo", "colaboracion", "teamwork"]),
    "Liderazgo": (T, ["liderazgo", "leadership"]),
    "Resolución de problemas": (T, ["resolucion de problemas", "solucion de problemas", "problem solving"]),
    "Pensamiento crítico": (T, ["pensamiento critico", "critical thinking"]),
    "Pensamiento analítico": (T, ["pensamiento analitico", "capacidad analitica"]),
    "Adaptabilidad": (T, ["adaptabilidad", "flexibilidad", "adaptacion al cambio"]),
    "Creatividad": (T, ["creatividad", "creativo", "creativa"]),
    "Organización": (T, ["organizacion", "orden"]),
    "Planeación": (T, ["planeacion", "planificacion"]),
    "Gestión del tiempo": (T, ["gestion del tiempo", "manejo del tiempo"]),
    "Atención al detalle": (T, ["atencion al detalle", "detallista"]),
    "Atención al cliente": (T, ["atencion al cliente", "servicio al cliente", "orientacion al cliente",
                                "customer service"]),
    "Negociación": (T, ["negociacion"]),
    "Proactividad": (T, ["proactividad", "proactivo", "proactiva", "iniciativa"]),
    "Responsabilidad": (T, ["responsabilidad", "responsable", "compromiso"]),
    "Aprendizaje continuo": (T, ["aprendizaje continuo", "disposicion para aprender", "autodidacta"]),
    "Empatía": (T, ["empatia"]),
    "Trabajo bajo presión": (T, ["trabajo bajo presion", "manejo de la presion"]),
    "Toma de decisiones": (T, ["toma de decisiones"]),
    "Inteligencia emocional": (T, ["inteligencia emocional"]),
    "Autonomía": (T, ["autonomia", "autogestion"]),
    "Orientación a resultados": (T, ["orientacion a resultados", "orientacion al logro"]),
    "Vocación de servicio": (T, ["vocacion de servicio"]),
    "Escucha activa": (T, ["escucha activa"]),
    "Puntualidad": (T, ["puntualidad"]),
    "Ética profesional": (T, ["etica profesional", "etica", "integridad"]),
    "Manejo de conflictos": (T, ["manejo de conflictos", "resolucion de conflictos"]),
    "Persuasión": (T, ["persuasion"]),
    "Pensamiento estratégico": (T, ["pensamiento estrategico", "vision estrategica"]),
}

_SYNONYM_INDEX: dict[str, str] = {}
for _canonical, (_kind, _synonyms) in SKILL_CATALOG.items():
    _SYNONYM_INDEX[_canonical.lower()] = _canonical
    for _s in _synonyms:
        _SYNONYM_INDEX[_s] = _canonical

# Sinónimos cortos o ambiguos: solo se aceptan si vienen como ítem de una lista, no en texto libre
_AMBIGUOUS = {"js", "ts", "ml", "ui", "ux", "go", "r", "next", "node", "spring", "agil", "redes", "office",
              "orden", "archivo", "bodega", "distribucion", "indicadores", "proveedores", "creativo", "creativa",
              "responsable", "compromiso", "iniciativa", "flexibilidad", "colaboracion", "construccion",
              "mecanica", "finanzas", "compras", "costos", "presupuesto", "presupuestos", "cartera", "ventas",
              "rest", "testing", "contenedores", "inventarios", "almacenamiento", "despachos", "impuestos",
              "conciliaciones"}
# Tipos que se buscan en texto libre (descripciones, perfil). Las transversales solo cuentan si el
# candidato las lista en HABILIDADES: "comunicación" en "Comunicación Social" no es una habilidad blanda.
_FREE_TEXT_KINDS = {H, C}
_LEVEL_RE = re.compile(
    r"\(?\b(?:nivel\s+)?(basico|basica|intermedio|intermedia|avanzado|avanzada|experto|experta)\b\)?", re.I)


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _key(text: str) -> str:
    return re.sub(r"\s+", " ", strip_accents(text).lower().strip())


def split_level(raw: str) -> tuple[str, str | None]:
    """'Excel avanzado' -> ('Excel', 'avanzado'); 'Python (básico)' -> ('Python', 'basico')."""
    text = unicodedata.normalize("NFC", raw)
    m = _LEVEL_RE.search(strip_accents(text))  # mismas posiciones: en NFC cada letra con tilde es 1 carácter
    if not m:
        return text.strip(), None
    word = m.group(1).lower()
    level = "basico" if word.startswith("basic") else "intermedio" if word.startswith("intermedi") else "avanzado"
    base = (text[: m.start()] + " " + text[m.end():]).strip(" .,-()")
    return re.sub(r"\s+", " ", base), level


def normalize_skill(raw: str) -> str:
    """Devuelve el nombre canónico; si no está en el catálogo, una versión limpia del texto."""
    key = _key(raw)
    if key in _SYNONYM_INDEX:
        return _SYNONYM_INDEX[key]
    cleaned = raw.strip().strip(".-•* ")
    return cleaned[:1].upper() + cleaned[1:] if cleaned else cleaned


def skill_kind(name: str) -> str | None:
    """Tipo según el catálogo, o None si la habilidad no está en él."""
    entry = SKILL_CATALOG.get(normalize_skill(name))
    return entry[0] if entry else None


def in_catalog(name: str) -> bool:
    return _key(name) in _SYNONYM_INDEX


def normalize_skills(raws: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for r in raws:
        if not r or not r.strip():
            continue
        n = normalize_skill(r)
        seen.setdefault(n.lower(), n)
    return list(seen.values())


def extract_skills_from_text(text: str, kinds: set[str] | None = None) -> list[str]:
    """Busca habilidades del catálogo en texto libre (modo reglas). Por defecto solo las técnicas."""
    kinds = kinds or _FREE_TEXT_KINDS
    norm = " " + _key(text) + " "
    found: list[str] = []
    for canonical, (kind, synonyms) in SKILL_CATALOG.items():
        if kind not in kinds:
            continue
        for s in [canonical.lower(), *synonyms]:
            s_key = _key(s)
            if s_key in _AMBIGUOUS:
                continue
            pattern = r"(?<![\w#+.])" + re.escape(s_key) + r"(?![\w#+])"
            if re.search(pattern, norm):
                found.append(canonical)
                break
    return found
