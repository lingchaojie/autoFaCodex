from pathlib import Path
from zipfile import ZipFile

import pytest
from pptx import Presentation

from autofacodex.contracts import SlideModel
from autofacodex.tools.slide_model_builder import build_initial_slide_model
from autofacodex.tools.pptx_generate import generate_pptx


def _model(slides: list[dict]) -> SlideModel:
    return SlideModel(slides=slides)


def test_generate_pptx_contains_expected_slides_and_editable_text(tmp_path: Path):
    model = _model(
        [
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
                        "w": 5,
                        "h": 1,
                        "style": {"font_size": 28},
                    }
                ],
                "raster_fallback_regions": [],
            },
            {
                "page_number": 2,
                "size": {"width": 10, "height": 7.5},
                "elements": [],
                "raster_fallback_regions": [],
            },
        ]
    )
    output = tmp_path / "candidate.pptx"

    generate_pptx(model, output)

    presentation = Presentation(output)
    assert len(presentation.slides) == len(model.slides)
    assert presentation.slides[0].shapes[0].text == "Editable Title"
    assert presentation.slides[0].shapes[0].text_frame.paragraphs[0].runs[0].font.size.pt == 28

    with ZipFile(output) as pptx:
        slide_xml = pptx.read("ppt/slides/slide1.xml").decode("utf-8")
    assert "<a:t>Editable Title</a:t>" in slide_xml
    assert "<p:pic>" not in slide_xml


def test_generate_pptx_rejects_mixed_slide_sizes(tmp_path: Path):
    model = _model(
        slides=[
            {
                "page_number": 1,
                "size": {"width": 10, "height": 7.5},
                "elements": [],
                "raster_fallback_regions": [],
            },
            {
                "page_number": 2,
                "size": {"width": 13.333, "height": 7.5},
                "elements": [],
                "raster_fallback_regions": [],
            },
        ]
    )

    with pytest.raises(ValueError, match="same size"):
        generate_pptx(model, tmp_path / "mixed.pptx")


def test_build_initial_slide_model_keeps_empty_slide_for_no_text_page():
    model = build_initial_slide_model(
        {
            "pages": [
                {"page_number": 1, "width": 200, "height": 100, "text": ""},
            ]
        }
    )

    assert len(model.slides) == 1
    assert model.slides[0].elements == []


def test_build_initial_slide_model_normalizes_slide_sizes_across_pages():
    model = build_initial_slide_model(
        {
            "pages": [
                {"page_number": 1, "width": 200, "height": 100, "text": "First"},
                {"page_number": 2, "width": 100, "height": 200, "text": "Second"},
            ]
        }
    )

    assert model.slides[0].size.width == pytest.approx(13.333)
    assert model.slides[0].size.height == pytest.approx(6.6665)
    assert model.slides[1].size == model.slides[0].size


@pytest.mark.parametrize(
    ("page", "message"),
    [
        ({"page_number": 1, "height": 100, "text": "Missing width"}, "width"),
        ({"page_number": 1, "width": 100, "text": "Missing height"}, "height"),
        ({"page_number": 1, "width": 0, "height": 100, "text": "Zero width"}, "width"),
        ({"page_number": 1, "width": 100, "height": 0, "text": "Zero height"}, "height"),
        ({"page_number": 1, "width": -1, "height": 100, "text": "Negative width"}, "width"),
        ({"page_number": 1, "width": 100, "height": -1, "text": "Negative height"}, "height"),
        ({"page_number": 1, "width": "wide", "height": 100, "text": "Bad width"}, "width"),
        ({"page_number": 1, "width": 100, "height": "tall", "text": "Bad height"}, "height"),
    ],
)
def test_build_initial_slide_model_rejects_invalid_dimensions(page: dict, message: str):
    with pytest.raises(ValueError, match=message):
        build_initial_slide_model({"pages": [page]})
