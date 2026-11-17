"""Convierte los CVs de ejemplo (samples/*.txt) a PDF para probar la carga real.

Uso: python scripts/make_sample_pdfs.py
"""

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

SAMPLES = Path(__file__).resolve().parents[2] / "samples"

for txt in SAMPLES.glob("*.txt"):
    pdf_path = txt.with_suffix(".pdf")
    c = canvas.Canvas(str(pdf_path), pagesize=LETTER)
    y = 750
    for i, line in enumerate(txt.read_text(encoding="utf-8").splitlines()):
        c.setFont("Helvetica-Bold" if i == 0 or line.isupper() else "Helvetica", 13 if i == 0 else 10)
        c.drawString(50, y, line)
        y -= 16
        if y < 60:
            c.showPage()
            y = 750
    c.save()
    print("PDF generado:", pdf_path.name)
