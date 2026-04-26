from pathlib import Path

from reportlab.pdfgen import canvas

from autofacodex.tools.pdf_extract import extract_pdf
from autofacodex.tools.pdf_render import render_pdf_pages


def make_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(400, 300))
    c.setFont("Helvetica", 24)
    c.drawString(72, 220, "Editable Title")
    c.rect(70, 120, 160, 60, stroke=1, fill=0)
    c.save()


def test_extract_pdf_text_and_page_size(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf)

    result = extract_pdf(pdf, tmp_path / "extracted")

    assert result["pages"][0]["page_number"] == 1
    assert "Editable Title" in result["pages"][0]["text"]


def test_render_pdf_pages_outputs_png(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf)

    renders = render_pdf_pages(pdf, tmp_path / "renders")

    assert len(renders) == 1
    assert renders[0].suffix == ".png"
    assert renders[0].is_file()
