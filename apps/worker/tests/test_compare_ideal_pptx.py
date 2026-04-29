from pathlib import Path

from pptx import Presentation

from autofacodex.evaluation.compare_ideal_pptx import compare_pptx_structure


def _pptx(path: Path, texts: list[str]) -> None:
    prs = Presentation()
    blank = prs.slide_layouts[6]
    for text in texts:
        slide = prs.slides.add_slide(blank)
        box = slide.shapes.add_textbox(914400, 914400, 3657600, 914400)
        box.text = text
    prs.save(path)


def test_compare_pptx_structure_reports_page_count_and_text_delta(tmp_path: Path):
    generated = tmp_path / "generated.pptx"
    ideal = tmp_path / "ideal.pptx"
    _pptx(generated, ["One"])
    _pptx(ideal, ["One", "Two"])

    result = compare_pptx_structure(generated, ideal)

    assert result["generated_slide_count"] == 1
    assert result["ideal_slide_count"] == 2
    assert result["slide_count_delta"] == -1
    assert result["pages"][0]["generated_text_runs"] == 1
    assert result["pages"][0]["ideal_text_runs"] == 1
