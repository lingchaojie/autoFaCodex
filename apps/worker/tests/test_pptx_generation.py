from pathlib import Path
from zipfile import ZipFile

from autofacodex.contracts import SlideModel
from autofacodex.tools.pptx_generate import generate_pptx


def test_generate_pptx_contains_editable_text(tmp_path: Path):
    model = SlideModel(
        slides=[
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
            }
        ]
    )
    output = tmp_path / "candidate.pptx"

    generate_pptx(model, output)

    with ZipFile(output) as pptx:
        slide_xml = pptx.read("ppt/slides/slide1.xml").decode("utf-8")
    assert "Editable Title" in slide_xml
