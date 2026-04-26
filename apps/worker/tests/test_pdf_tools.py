import json
import math
from pathlib import Path

import fitz
import pytest
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from autofacodex.tools.pdf_extract import extract_pdf
from autofacodex.tools.pdf_render import render_pdf_pages


def make_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(400, 300))
    c.setFont("Helvetica", 24)
    c.drawString(72, 220, "Editable Title")
    c.rect(70, 120, 160, 60, stroke=1, fill=0)
    c.save()


def make_pdf_with_image(path: Path, image_path: Path) -> None:
    image = Image.new("RGB", (12, 10), color=(220, 20, 60))
    image.save(image_path)

    c = canvas.Canvas(str(path), pagesize=(400, 300))
    c.drawImage(ImageReader(str(image_path)), 80, 140, width=120, height=100)
    c.save()


def test_extract_pdf_text_and_page_size(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf)

    result = extract_pdf(pdf, tmp_path / "extracted")

    page = result["pages"][0]
    assert page["page_number"] == 1
    assert page["width"] == 400
    assert page["height"] == 300
    assert page["drawing_count"] >= 1
    assert "Editable Title" in page["text"]


def test_extract_pdf_writes_pages_json_matching_result(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    output_dir = tmp_path / "extracted"
    make_pdf(pdf)

    result = extract_pdf(pdf, output_dir)

    pages_json = output_dir / "pages.json"
    assert pages_json.is_file()
    assert json.loads(pages_json.read_text(encoding="utf-8")) == result


def test_extract_pdf_with_image_writes_json_serializable_metadata(tmp_path: Path):
    pdf = tmp_path / "image.pdf"
    make_pdf_with_image(pdf, tmp_path / "sample.png")

    result = extract_pdf(pdf, tmp_path / "extracted")

    assert result["pages"][0]["image_count"] >= 1
    pages_json = tmp_path / "extracted" / "pages.json"
    saved = json.loads(pages_json.read_text(encoding="utf-8"))
    assert saved == result
    image_blocks = [
        block
        for block in result["pages"][0]["text_blocks"]
        if block["type"] == "image"
    ]
    assert image_blocks
    assert all("image" not in block for block in image_blocks)


def test_render_pdf_pages_outputs_png(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf)

    renders = render_pdf_pages(pdf, tmp_path / "renders")

    assert len(renders) == 1
    assert renders[0].suffix == ".png"
    assert renders[0].is_file()


def test_render_pdf_pages_output_dimensions_reflect_zoom(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf)

    renders = render_pdf_pages(pdf, tmp_path / "renders", zoom=1.5)

    pixmap = fitz.Pixmap(renders[0])
    assert pixmap.width == 600
    assert pixmap.height == 450


@pytest.mark.parametrize("zoom", [0, -1, math.nan, 8.1])
def test_render_pdf_pages_rejects_invalid_zoom_before_creating_output(
    tmp_path: Path, zoom: float
):
    pdf = tmp_path / "sample.pdf"
    output_dir = tmp_path / "renders"
    make_pdf(pdf)

    with pytest.raises(ValueError, match="zoom"):
        render_pdf_pages(pdf, output_dir, zoom=zoom)

    assert not output_dir.exists()
