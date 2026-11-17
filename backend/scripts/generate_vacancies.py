"""Genera un dataset curado de vacantes FICTICIAS (enfoque Colombia) con formatos
heterogéneos a propósito (salarios, ciudades, modalidades escritas de distintas formas)
para que el Agente de Vacantes tenga que normalizarlas.

Uso: python scripts/generate_vacancies.py
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(2026)
OUT = Path(__file__).resolve().parent.parent / "app" / "infrastructure" / "data" / "vacancies_raw.json"

COMPANIES = ["Andes Tech S.A.S.", "Cafetera Digital", "Fintech Cóndor", "Logística Paisa", "Salud360 IPS",
             "Retail Caribe", "EduNube", "AgroData Colombia", "Banco Ficticio del Valle", "Seguros Orquídea",
             "Movilidad Verde", "Energía Llanera", "Telco Pacífico", "Comercio Ágil", "Grupo Montaña Azul"]
CITIES = ["Medellín", "medellin", "Bogotá D.C.", "bogota", "Cali", "Barranquilla", "Envigado",
          "Bucaramanga", "Pereira", "Itagüí", "Cartagena"]
MODALITIES = {"presencial": ["Presencial", "En sitio", "presencial"],
              "remoto": ["Remoto", "Teletrabajo", "100% remoto", "Home office"],
              "hibrido": ["Híbrido", "Mixto", "híbrido (3 días oficina)"]}

ROLES = [
    # (título, seniority_raw, must, nice, salario base millones)
    ("Desarrollador Backend", ["Junior", "Semi Senior", "Senior"], ["Python", "SQL", "REST APIs"],
     ["Docker", "FastAPI", "AWS", "PostgreSQL"], [3.0, 5.5, 9.0]),
    ("Desarrollador Backend Node.js", ["Junior", "SSr", "Sr"], ["javascript", "node", "REST APIs"],
     ["TypeScript", "MongoDB", "Docker"], [3.2, 5.8, 9.5]),
    ("Desarrollador Frontend", ["Jr", "Semi Senior", "Senior"], ["JavaScript", "React", "HTML", "CSS"],
     ["TypeScript", "Next.js", "Tailwind"], [3.0, 5.0, 8.5]),
    ("Desarrollador Full Stack", ["Junior", "Semi Senior", "Senior"], ["JavaScript", "React", "Node.js", "SQL"],
     ["TypeScript", "Docker", "PostgreSQL", "Git"], [3.5, 6.0, 10.0]),
    ("Desarrollador Java", ["Junior", "Semi Senior", "Senior"], ["Java", "Spring Boot", "SQL"],
     ["Microservicios", "Docker", "Kubernetes"], [3.3, 6.0, 10.0]),
    ("Desarrollador .NET", ["Junior", "Semi Senior", "Senior"], ["C#", ".NET", "SQL"],
     ["Azure", "Microservicios"], [3.3, 5.8, 9.5]),
    ("Ingeniero de Datos", ["Junior", "Semi Senior", "Senior"], ["Python", "SQL", "Pandas"],
     ["AWS", "Docker", "PostgreSQL"], [3.8, 6.5, 11.0]),
    ("Analista de Datos", ["Practicante", "Junior", "Semi Senior"], ["SQL", "Excel avanzado", "Power BI"],
     ["Python", "Estadística", "Tableau"], [1.8, 3.2, 5.0]),
    ("Ingeniero DevOps", ["Junior", "Semi Senior", "Senior"], ["Docker", "Linux", "CI/CD"],
     ["Kubernetes", "AWS", "Git"], [4.0, 7.0, 11.5]),
    ("Analista QA", ["Junior", "Semi Senior", "Senior"], ["QA manual", "Pruebas unitarias"],
     ["Selenium", "Cypress", "Scrum"], [2.5, 4.2, 7.0]),
    ("Diseñador UX/UI", ["Junior", "Semi Senior", "Senior"], ["Figma", "UX/UI"],
     ["HTML", "CSS", "Scrum"], [2.8, 4.8, 7.5]),
    ("Desarrollador IA / LLM", ["Junior", "Semi Senior", "Senior"], ["Python", "LangChain", "REST APIs"],
     ["Machine Learning", "Docker", "FastAPI"], [4.0, 7.0, 12.0]),
    ("Practicante de Desarrollo de Software", ["Practicante"], ["Git", "Python"],
     ["JavaScript", "SQL"], [1.3]),
    ("Asesor Comercial", ["Junior", "Semi Senior"], ["Ventas", "Atención al cliente"],
     ["Excel", "Negociación", "Comunicación"], [1.6, 2.5]),
    ("Auxiliar Contable", ["Junior", "Semi Senior"], ["Contabilidad", "Excel intermedio"],
     ["SAP", "Siigo", "Atención al detalle"], [1.8, 2.8]),
    ("Analista de Logística", ["Junior", "Semi Senior"], ["Excel avanzado", "Control de inventarios", "ERP"],
     ["SAP", "Power BI", "Power Query", "Organización"], [2.6, 3.8]),
    ("Coordinador de Operaciones", ["Semi Senior", "Senior"], ["Excel", "Control de inventarios", "Indicadores KPI"],
     ["SAP", "ERP"], [3.8, 5.5]),
    ("Auxiliar de Bodega", ["Junior"], ["Control de inventarios"], ["Excel"], [1.5]),
    ("Asistente de Marketing Digital", ["Junior"], ["Redes sociales", "Canva"], ["Excel", "Creación de contenido"],
     [1.8]),
    ("Community Manager", ["Junior", "Semi Senior"], ["Redes sociales", "Creación de contenido"],
     ["Canva", "Figma", "Creatividad"], [2.0, 3.2]),
    ("Auxiliar de Soporte TI", ["Practicante", "Junior"], ["Soporte técnico"],
     ["Redes", "Windows", "Excel", "Atención al cliente"],
     [1.4, 2.0]),
    ("Analista de BI", ["Junior", "Semi Senior"], ["SQL", "Power BI"], ["Python", "Excel", "DAX"], [3.2, 5.2]),
]


def salary_text(base_millions: float) -> str | None:
    low = int(base_millions * 1_000_000 / 100_000) * 100_000
    high = int(low * random.choice([1.2, 1.3, 1.4]) / 100_000) * 100_000
    style = random.randint(0, 5)
    if style == 0:
        return f"${low:,.0f} - ${high:,.0f}".replace(",", ".")
    if style == 1:
        return f"{low / 1e6:.1f}M a {high / 1e6:.1f}M".replace(".0M", "M")
    if style == 2:
        return f"Hasta {high / 1e6:.1f} millones".replace(".0 ", " ")
    if style == 3:
        return f"{low} - {high} COP"
    if style == 4:
        return "A convenir"
    return f"$ {low:,.0f}".replace(",", ".")


def min_education(title: str, lvl: str) -> str:
    """Nivel educativo mínimo típico del cargo (escala colombiana)."""
    if lvl == "Practicante":
        return "Técnico"
    if "Bodega" in title:
        return "Bachiller"
    if title.startswith(("Auxiliar", "Asistente", "Asesor")):
        return "Técnico"
    if title.startswith(("Analista QA", "Diseñador", "Community")) or lvl in ("Junior", "Jr"):
        return "Tecnólogo"
    return "Profesional"


vacancies = []
today = date(2026, 11, 15)
n = 0
for title, levels, must, nice, salaries in ROLES:
    for lvl, base in zip(levels, salaries, strict=True):
        for _ in range(random.choice([1, 2])):
            n += 1
            mod_key = random.choices(["presencial", "remoto", "hibrido"], weights=[3, 3, 4])[0]
            is_intern = lvl == "Practicante"
            tech = title.startswith(("Desarrollador", "Ingeniero", "Analista de Datos", "Diseñador"))
            english = random.choice(["B1", "B2"]) if tech and lvl in ("Semi Senior", "SSr", "Senior", "Sr") \
                and random.random() < 0.6 else None
            vacancies.append({
                "id": f"VAC-{n:03d}",
                "titulo": title if "Practicante" in title else f"{title} {lvl}",
                "empresa": random.choice(COMPANIES),
                "ubicacion": random.choice(CITIES) + random.choice(["", ", Colombia"]),
                "modalidad": random.choice(MODALITIES[mod_key]),
                "salario": salary_text(base),
                "nivel": lvl,
                "requisitos": ", ".join(must + ([f"Inglés {english}"] if english else [])),
                "deseables": ", ".join(random.sample(nice, k=min(len(nice), random.randint(1, 3)))),
                "descripcion": f"Buscamos {title.lower()} nivel {lvl.lower()} para unirse a nuestro equipo. "
                               f"Trabajarás con {', '.join(must)} en proyectos de impacto para clientes en Colombia.",
                "jornada": random.choice(["Medio tiempo", "Tiempo completo"]) if is_intern or title.startswith("Asesor")
                else "Tiempo completo",
                "tipo_contrato": "Contrato de aprendizaje" if is_intern else random.choice(
                    ["Término indefinido", "Término indefinido", "Término fijo", "Prestación de servicios"]),
                "educacion_minima": min_education(title, lvl),
                "requiere_viajar": title.startswith(("Asesor", "Coordinador")) or random.random() < 0.08,
                "fecha_publicacion": (today - timedelta(days=random.randint(0, 20))).isoformat(),
                "fuente": "dataset_curado",
            })

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(vacancies, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"{len(vacancies)} vacantes escritas en {OUT}")
