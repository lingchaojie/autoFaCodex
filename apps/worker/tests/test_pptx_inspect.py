from pathlib import Path

from PIL import Image

from autofacodex.contracts import SlideModel
from autofacodex.tools.pptx_generate import generate_pptx
from autofacodex.tools.pptx_inspect import inspect_pptx_editability


def _model(slide: dict) -> SlideModel:
    return SlideModel(slides=[slide])


def test_inspect_pptx_returns_editable_text_content(tmp_path: Path):
    model = _model(
        {
            "page_number": 1,
            "size": {"width": 10, "height": 7.5},
            "elements": [
                {
                    "id": "title",
                    "type": "text",
                    "text": "Editable Title",
                    "x": 1,
                    "y": 1,
                    "w": 4,
                    "h": 0.6,
                    "style": {"font_size": 24},
                }
            ],
            "raster_fallback_regions": [],
        }
    )
    output = tmp_path / "candidate.pptx"
    generate_pptx(model, output)

    inspection = inspect_pptx_editability(output)

    page = inspection["pages"][0]
    assert page["text"] == "Editable Title"
    assert page["text_runs"] == 1
    assert page["pictures"] == 0
    assert page["largest_picture_area_ratio"] == 0
    assert page["has_full_page_picture"] is False


def test_inspect_pptx_detects_full_page_picture(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (1200, 675), color=(240, 240, 240)).save(image_path)
    model = _model(
        {
            "page_number": 1,
            "size": {"width": 13.333, "height": 7.5},
            "elements": [
                {
                    "id": "page-image",
                    "type": "image",
                    "source": str(image_path),
                    "x": 0,
                    "y": 0,
                    "w": 13.333,
                    "h": 7.5,
                }
            ],
            "raster_fallback_regions": [],
        }
    )
    output = tmp_path / "candidate.pptx"
    generate_pptx(model, output)

    inspection = inspect_pptx_editability(output)

    page = inspection["pages"][0]
    assert page["pictures"] == 1
    assert page["largest_picture_area_ratio"] > 0.98
    assert page["has_full_page_picture"] is True
