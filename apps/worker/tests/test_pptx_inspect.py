from pathlib import Path

import pytest
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


def test_inspect_pptx_separates_text_runs_from_different_shapes(tmp_path: Path):
    model = _model(
        {
            "page_number": 1,
            "size": {"width": 10, "height": 7.5},
            "elements": [
                {
                    "id": "footer",
                    "type": "text",
                    "text": "Materials",
                    "x": 1,
                    "y": 1,
                    "w": 3,
                    "h": 0.4,
                },
                {
                    "id": "date",
                    "type": "text",
                    "text": "2024",
                    "x": 1,
                    "y": 2,
                    "w": 3,
                    "h": 0.4,
                },
            ],
            "raster_fallback_regions": [],
        }
    )
    output = tmp_path / "candidate.pptx"
    generate_pptx(model, output)

    inspection = inspect_pptx_editability(output)

    page = inspection["pages"][0]
    assert page["text"] == "Materials\n2024"
    assert page["text_runs"] == 2


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


def test_inspect_pptx_detects_tiled_full_page_pictures(tmp_path: Path):
    image_path = tmp_path / "tile.png"
    Image.new("RGB", (600, 400), color=(240, 240, 240)).save(image_path)
    elements = []
    for index, (x, y) in enumerate(
        [(0, 0), (5, 0), (0, 3.75), (5, 3.75)], start=1
    ):
        elements.append(
            {
                "id": f"tile-{index}",
                "type": "image",
                "source": str(image_path),
                "x": x,
                "y": y,
                "w": 5,
                "h": 3.75,
            }
        )
    model = _model(
        {
            "page_number": 1,
            "size": {"width": 10, "height": 7.5},
            "elements": elements,
            "raster_fallback_regions": [],
        }
    )
    output = tmp_path / "candidate.pptx"
    generate_pptx(model, output)

    inspection = inspect_pptx_editability(output)

    page = inspection["pages"][0]
    assert page["pictures"] == 4
    assert page["largest_picture_area_ratio"] == pytest.approx(0.25, abs=0.01)
    assert page["picture_coverage_ratio"] > 0.98
    assert page["has_full_page_picture"] is True


def test_inspect_pptx_reports_text_box_count_and_geometries(tmp_path: Path):
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
                },
                {
                    "id": "subtitle",
                    "type": "text",
                    "text": "Editable Subtitle",
                    "x": 2,
                    "y": 2,
                    "w": 3,
                    "h": 0.4,
                    "style": {"font_size": 14},
                },
            ],
            "raster_fallback_regions": [],
        }
    )
    output = tmp_path / "candidate.pptx"
    generate_pptx(model, output)

    inspection = inspect_pptx_editability(output)

    page = inspection["pages"][0]
    assert page["text_box_count"] == 2
    assert page["text_box_geometries"] == [
        {"x": pytest.approx(1), "y": pytest.approx(1), "w": pytest.approx(4), "h": pytest.approx(0.6)},
        {"x": pytest.approx(2), "y": pytest.approx(2), "w": pytest.approx(3), "h": pytest.approx(0.4)},
    ]
