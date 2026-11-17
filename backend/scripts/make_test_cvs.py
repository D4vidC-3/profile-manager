"""Genera 10 hojas de vida FICTICIAS para probar el Agente de Perfil
(completas, a medias, incompletas, formato libre, en inglés, dos columnas...).

Uso: python scripts/make_test_cvs.py   -> samples/pruebas/*.pdf y *.txt
Todos los nombres, documentos, correos (@example.com) y teléfonos son inventados.
"""

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parents[2] / "samples" / "pruebas"

CVS: dict[str, str] = {
    # 1. COMPLETA - plantilla recomendada, todos los campos
    "01_completa_plantilla_valentina": """VALENTINA OSORIO RESTREPO
Ingeniera de Datos Semi Senior
Medellín, Antioquia | valentina.osorio.demo@example.com | +57 301 234 5678
linkedin.com/in/valentina-osorio-demo

PERFIL
Ingeniera de datos con 4 años construyendo pipelines en Python y SQL sobre AWS. Experiencia en modelado de datos, ETL y tableros en Power BI para áreas de negocio.

EXPERIENCIA
Ingeniera de Datos | Fintech Cóndor | 2023 - Actual
Diseño de pipelines ETL con Python, Pandas y Airflow sobre AWS. Modelado en PostgreSQL. Contenedores con Docker.
Analista de Datos | Retail Caribe | 2021 - 2023
Tableros en Power BI, consultas SQL complejas y automatización de reportes en Excel.

EDUCACIÓN
Ingeniería Industrial | Universidad Nacional de Colombia | 2021
Especialización en Analítica de Datos | Universidad EAFIT | 2023

HABILIDADES
Python, SQL, Pandas, PostgreSQL, AWS, Docker, Power BI, Excel, Git, Estadística

IDIOMAS
Español nativo
Inglés C1

""",
    # 2. COMPLETA - formato libre narrativo (sin secciones estándar)
    "02_completa_libre_santiago": """Santiago Herrera Mejía
santiago.herrera.demo@example.com · 315 678 9012 · Bogotá D.C.

Hola, soy desarrollador full stack con unos 3 años de experiencia. Actualmente trabajo en Comercio Ágil
(desde 2023) construyendo una plataforma de pedidos con React, TypeScript y Node.js, desplegada en Docker.
Antes estuve en una agencia digital, Pixel Andino, entre 2022 y 2023, haciendo sitios con JavaScript, HTML y CSS.

Me gradué como Ingeniero de Software de la Pontificia Universidad Javeriana en 2022.
Hablo inglés a nivel B2.

""",
    # 3. A MEDIAS - tiene experiencia y skills, pero sin contacto ni expectativas
    "03_media_sin_contacto_camila": """CAMILA ANDREA PATIÑO
Desarrolladora Java

EXPERIENCIA
Desarrolladora Java | Banco Ficticio del Valle | 2020 - 2024
Microservicios con Spring Boot, integración con bases de datos SQL y despliegues con Kubernetes.
Desarrolladora Junior | Logística Paisa | 2019 - 2020
Mantenimiento de aplicaciones Java y pruebas unitarias con JUnit.

EDUCACIÓN
Ingeniería de Sistemas | Universidad del Valle | 2019

HABILIDADES
Java, Spring Boot, SQL, Microservicios, Kubernetes, Git, JUnit
""",
    # 4. A MEDIAS - contacto completo pero sin experiencia (recién graduado)
    "04_media_recien_graduado_juan": """Juan David Cárdenas
Cali, Valle del Cauca
juan.cardenas.demo@example.com | 318 222 3344

PERFIL
Recién graduado de Tecnología en Sistemas, con muchas ganas de aprender. Hice proyectos académicos
con Python y bases de datos MySQL, y un proyecto de grado de una app web con Django.

EDUCACIÓN
Tecnólogo en Sistemas de Información | Universidad Santiago de Cali | 2025
Bachiller académico | Colegio Santa Librada | 2021

HABILIDADES
Python, Django, MySQL, HTML, CSS, Git

""",
    # 5. INCOMPLETA - muy corta, casi sin información
    "05_incompleta_minima_pedro": """Pedro Gómez
pedro.gomez.demo@example.com

Trabajo en sistemas hace un tiempo. Sé de computadores y redes.
""",
    # 6. INCOMPLETA - solo una lista de habilidades, sin nombre claro
    "06_incompleta_solo_skills": """HOJA DE VIDA

HABILIDADES
React, JavaScript, CSS, Figma, Git

Contacto: 320 111 2233
""",
    # 7. COMPLETA - en inglés (prueba de idioma)
    "07_completa_ingles_laura": """LAURA BENÍTEZ
Senior QA Automation Engineer
Bucaramanga, Colombia | laura.benitez.demo@example.com | +57 312 444 5566
linkedin.com/in/laura-benitez-demo

SUMMARY
QA engineer with 7 years of experience in test automation for web and mobile apps using Selenium,
Cypress and CI/CD pipelines. Strong background in Scrum teams.

EXPERIENCE
QA Automation Lead | Telco Pacífico | 2021 - Present
Built Cypress and Selenium test suites, integrated in GitHub Actions. Led a team of 4 testers.
QA Analyst | EduNube | 2018 - 2021
Manual and functional testing, API testing with Postman, defect tracking in Jira.

EDUCATION
Systems Engineering | Universidad Industrial de Santander | 2018

SKILLS
Selenium, Cypress, Python, JavaScript, CI/CD, Scrum, SQL, Git

LANGUAGES
Spanish native, English C1
""",
    # 8. A MEDIAS - cambio de carrera (perfil no técnico hacia tecnología)
    "08_media_cambio_carrera_andrea": """ANDREA LUCÍA MORENO
Barranquilla | andrea.moreno.demo@example.com | 300 987 6543

PERFIL
Contadora pública con 6 años de experiencia que está haciendo transición hacia el análisis de datos.
Terminé un bootcamp de analítica donde aprendí SQL, Power BI y Python básico.

EXPERIENCIA
Contadora | Seguros Orquídea | 2019 - 2025
Cierres contables, conciliaciones, reportes NIIF y manejo de SAP. Automatización de reportes en Excel.
Auxiliar Contable | Comercio Ágil | 2017 - 2019
Registro de facturas y apoyo en declaraciones tributarias.

EDUCACIÓN
Contaduría Pública | Universidad del Norte | 2017
Bootcamp de Analítica de Datos | Academia Datos Caribe | 2025

HABILIDADES
Contabilidad, Excel, SAP, SQL, Power BI, Python

""",
    # 9. COMPLETA - senior con mucha experiencia y fechas en formato mes/año
    "09_completa_senior_ricardo": """RICARDO ALEJANDRO VÉLEZ
Arquitecto de Software / Líder Técnico Backend
Envigado, Antioquia | ricardo.velez.demo@example.com | +57 304 555 7788
linkedin.com/in/ricardo-velez-demo

PERFIL
Líder técnico con más de 10 años diseñando arquitecturas de microservicios en .NET y Java para banca
y seguros. Mentor de equipos, enfoque en calidad, observabilidad y nube Azure.

EXPERIENCIA
Arquitecto de Software | Grupo Montaña Azul | Ene 2020 - Actual
Definición de arquitectura de microservicios en .NET y Azure, Kubernetes y CI/CD.
Líder Técnico Backend | Banco Ficticio del Valle | Mar 2016 - Dic 2019
Liderazgo de 8 desarrolladores, migración de monolito Java a Spring Boot.
Desarrollador Senior | Seguros Orquídea | Feb 2013 - Feb 2016
Desarrollo en C# y SQL Server, integración con SAP.

EDUCACIÓN
Ingeniería Informática | Universidad de Antioquia | 2012
Maestría en Ingeniería de Software | Universidad EAFIT | 2018

HABILIDADES
C#, .NET, Java, Spring Boot, Azure, Kubernetes, Docker, Microservicios, SQL, CI/CD, Scrum

IDIOMAS
Español nativo
Inglés C1

""",
    # 10. A MEDIAS - diseño a dos columnas en el PDF (prueba de extracción)
    "10_media_dos_columnas_mateo": """@@COLUMNAS@@
MATEO RÍOS
Diseñador UX/UI
Pereira
mateo.rios.demo@example.com
311 765 4321
||
EXPERIENCIA
Diseñador UX/UI | EduNube | 2022 - Actual
Investigación con usuarios, prototipos en Figma y sistemas de diseño.
Diseñador Gráfico | Cafetera Digital | 2020 - 2022
Piezas digitales y apoyo en maquetación HTML y CSS.
EDUCACIÓN
Diseño Visual | Universidad de Caldas | 2020
HABILIDADES
Figma, UX/UI, HTML, CSS, Scrum
""",
}


def write_pdf(path: Path, text: str) -> None:
    c = canvas.Canvas(str(path), pagesize=LETTER)
    if text.startswith("@@COLUMNAS@@"):
        left, right = text.replace("@@COLUMNAS@@\n", "").split("||\n")
        for x, block in ((40, left), (230, right)):
            y = 750
            for line in block.strip().splitlines():
                c.setFont("Helvetica-Bold" if line.isupper() else "Helvetica", 9)
                c.drawString(x, y, line[:60] if x == 230 else line[:30])
                y -= 14
        c.save()
        return
    y = 750
    for i, line in enumerate(text.splitlines()):
        bold = i == 0 or (line.isupper() and len(line) < 40)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 13 if i == 0 else 9.5)
        c.drawString(45, y, line)
        y -= 15
        if y < 50:
            c.showPage()
            y = 750
    c.save()


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in CVS.items():
        clean = text.replace("@@COLUMNAS@@\n", "").replace("||\n", "")
        (OUT / f"{name}.txt").write_text(clean, encoding="utf-8")
        write_pdf(OUT / f"{name}.pdf", text)
    print(f"{len(CVS)} hojas de vida generadas en {OUT}")
