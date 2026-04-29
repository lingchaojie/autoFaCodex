import json
from pathlib import Path

import pytest
from PIL import Image

from autofacodex.contracts import SlideModel, ValidatorReport
from autofacodex.tools.validate_candidate import validate_candidate


def _write_task(
    task_dir: Path,
    *,
    ppt_text: str,
    full_page_picture: bool = False,
    model_page_number: int = 1,
    model_elements: list[dict] | None = None,
) -> None:
    (task_dir / "renders" / "pdf").mkdir(parents=True)
    (task_dir / "output").mkdir(parents=True)
    (task_dir / "slides").mkdir(parents=True)
    (task_dir / "extracted").mkdir(parents=True)
    Image.new("RGB", (20, 20), color=(255, 255, 255)).save(
        task_dir / "renders" / "pdf" / "page-001.png"
    )
    (task_dir / "output" / "candidate.v1.pptx").write_bytes(b"pptx")
    (task_dir / "extracted" / "pages.json").write_text(
        json.dumps(
            {"pages": [{"page_number": 1, "width": 20, "height": 20, "text": "Editable Title"}]}
        ),
        encoding="utf-8",
    )
    model = SlideModel(
        slides=[
            {
                "page_number": model_page_number,
                "size": {"width": 10, "height": 7.5},
                "elements": model_elements or [],
                "raster_fallback_regions": [],
            }
        ]
    )
    (task_dir / "slides" / "slide-model.v1.json").write_text(
        model.model_dump_json(indent=2), encoding="utf-8"
    )
    inspection = {
        "pages": [
            {
                "slide": "ppt/slides/slide1.xml",
                "text_runs": 1 if ppt_text else 0,
                "pictures": 1 if full_page_picture else 0,
                "shapes": 1,
                "tables": 0,
                "text": ppt_text,
                "largest_picture_area_ratio": 0.99 if full_page_picture else 0,
                "has_full_page_picture": full_page_picture,
            }
        ]
    }
    (task_dir / "reports").mkdir(parents=True)
    (task_dir / "reports" / "inspection.v1.json").write_text(
        json.dumps(inspection), encoding="utf-8"
    )


def _stub_validation_tools(task_dir: Path, monkeypatch) -> None:
    rendered_page = task_dir / "output" / "rendered-pages-v1" / "page-001.png"

    monkeypatch.setattr(
        "autofacodex.tools.validate_candidate.render_pptx_pages",
        lambda *_args, **_kwargs: type(
            "RenderResult",
            (),
            {
                "page_images": [rendered_page],
                "output_pdf": task_dir / "output" / "rendered-pdf-v1" / "candidate.v1.pdf",
            },
        )(),
    )
    monkeypatch.setattr("autofacodex.tools.validate_candidate.compare_images", lambda *_args: 0.96)
    monkeypatch.setattr(
        "autofacodex.tools.validate_candidate.extract_diff_regions",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "autofacodex.tools.validate_candidate.write_diff_image", lambda *_args: _args[2]
    )
    monkeypatch.setattr(
        "autofacodex.tools.validate_candidate.write_compare_image", lambda *_args: _args[2]
    )
    monkeypatch.setattr(
        "autofacodex.tools.validate_candidate.inspect_pptx_editability",
        lambda *_args: json.loads(
            (task_dir / "reports" / "inspection.v1.json").read_text(encoding="utf-8")
        ),
    )


def test_validate_candidate_passes_high_quality_editable_page(tmp_path: Path, monkeypatch):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_task(task_dir, ppt_text="Editable Title")
    _stub_validation_tools(task_dir, monkeypatch)

    report = validate_candidate(task_dir, attempt=1)

    assert report.aggregate_status == "pass"
    assert report.pages[0].status == "pass"
    assert report.pages[0].visual_score == 0.96
    assert report.pages[0].text_coverage_score == 1.0
    assert report.pages[0].evidence_paths == {
        "pdf_render": "renders/pdf/page-001.png",
        "ppt_render": "output/rendered-pages-v1/page-001.png",
        "diff": "output/diagnostics-v1/page-001-diff.png",
        "compare": "output/diagnostics-v1/page-001-compare.png",
        "inspection": "reports/inspection.v1.json",
        "text_coverage": "reports/text-coverage.v1.json",
    }
    text_coverage = json.loads(
        (task_dir / "reports" / "text-coverage.v1.json").read_text(encoding="utf-8")
    )
    assert text_coverage == [
        {
            "page_number": 1,
            "score": 1.0,
            "missing_ratio": 0.0,
            "missing_text": "",
            "source_length": 13,
            "candidate_length": 13,
        }
    ]
    assert (task_dir / "reports" / "validator.v1.json").is_file()
    ValidatorReport.model_validate_json(
        (task_dir / "reports" / "validator.v1.json").read_text(encoding="utf-8")
    )


def test_validate_candidate_rejects_full_page_picture(tmp_path: Path, monkeypatch):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_task(task_dir, ppt_text="Editable Title", full_page_picture=True)
    _stub_validation_tools(task_dir, monkeypatch)

    report = validate_candidate(task_dir, attempt=1)

    assert report.aggregate_status == "repair_needed"
    assert report.pages[0].status == "repair_needed"
    assert report.pages[0].raster_fallback_ratio == pytest.approx(0.99)
    assert any(issue.type == "editability" for issue in report.pages[0].issues)


def test_validate_candidate_allows_declared_pdf_background_picture_with_editable_foreground(
    tmp_path: Path, monkeypatch
):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_task(
        task_dir,
        ppt_text="Editable Title",
        full_page_picture=True,
        model_elements=[
            {
                "id": "background",
                "type": "image",
                "source": "extracted/objects/images/background.png",
                "x": 0,
                "y": 0,
                "w": 10,
                "h": 7.5,
                "style": {"role": "background"},
            },
            {
                "id": "title",
                "type": "text",
                "text": "Editable Title",
                "x": 1,
                "y": 1,
                "w": 4,
                "h": 0.5,
            },
        ],
    )
    _stub_validation_tools(task_dir, monkeypatch)

    report = validate_candidate(task_dir, attempt=1)

    assert report.aggregate_status == "pass"
    assert report.pages[0].status == "pass"
    assert report.pages[0].raster_fallback_ratio == 0
    assert report.pages[0].editable_score == 1.0


def test_validate_candidate_allows_large_declared_background_with_editable_foreground(
    tmp_path: Path, monkeypatch
):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_task(
        task_dir,
        ppt_text="Editable Title",
        model_elements=[
            {
                "id": "background",
                "type": "image",
                "source": "extracted/objects/images/background.png",
                "x": 0,
                "y": 0.5,
                "w": 10,
                "h": 6.5,
                "style": {"role": "background"},
            },
            {
                "id": "title",
                "type": "text",
                "text": "Editable Title",
                "x": 1,
                "y": 1,
                "w": 4,
                "h": 0.5,
            },
        ],
    )
    (task_dir / "reports" / "inspection.v1.json").write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "slide": "ppt/slides/slide1.xml",
                        "text_runs": 1,
                        "pictures": 1,
                        "shapes": 1,
                        "tables": 0,
                        "text": "Editable Title",
                        "largest_picture_area_ratio": 0.86,
                        "picture_coverage_ratio": 0.86,
                        "has_full_page_picture": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _stub_validation_tools(task_dir, monkeypatch)

    report = validate_candidate(task_dir, attempt=1)

    assert report.aggregate_status == "pass"
    assert report.pages[0].status == "pass"
    assert report.pages[0].raster_fallback_ratio == 0


def test_validate_candidate_rejects_tiled_full_page_picture_coverage(
    tmp_path: Path, monkeypatch
):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_task(task_dir, ppt_text="Editable Title")
    (task_dir / "reports" / "inspection.v1.json").write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "slide": "ppt/slides/slide1.xml",
                        "text_runs": 1,
                        "pictures": 4,
                        "shapes": 1,
                        "tables": 0,
                        "text": "Editable Title",
                        "largest_picture_area_ratio": 0.25,
                        "picture_coverage_ratio": 0.99,
                        "has_full_page_picture": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _stub_validation_tools(task_dir, monkeypatch)

    report = validate_candidate(task_dir, attempt=1)

    assert report.aggregate_status == "repair_needed"
    assert report.pages[0].status == "repair_needed"
    assert report.pages[0].raster_fallback_ratio == pytest.approx(0.99)
    assert any(issue.type == "editability" for issue in report.pages[0].issues)


def test_validate_candidate_allows_many_bounded_images_without_fallback_regions(
    tmp_path: Path, monkeypatch
):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_task(task_dir, ppt_text="Editable Title")
    (task_dir / "reports" / "inspection.v1.json").write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "slide": "ppt/slides/slide1.xml",
                        "text_runs": 1,
                        "pictures": 8,
                        "shapes": 1,
                        "tables": 0,
                        "text": "Editable Title",
                        "largest_picture_area_ratio": 0.2,
                        "total_picture_area_ratio": 0.8,
                        "picture_coverage_ratio": 0.4,
                        "has_full_page_picture": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _stub_validation_tools(task_dir, monkeypatch)

    report = validate_candidate(task_dir, attempt=1)

    assert report.aggregate_status == "pass"
    assert report.pages[0].status == "pass"
    assert report.pages[0].raster_fallback_ratio == pytest.approx(0.4)


def test_validate_candidate_adds_visual_diff_region_and_repair_hint(
    tmp_path: Path, monkeypatch
):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_task(task_dir, ppt_text="Editable Title")
    _stub_validation_tools(task_dir, monkeypatch)

    monkeypatch.setattr("autofacodex.tools.validate_candidate.compare_images", lambda *_args: 0.86)
    def fake_extract_diff_regions(*_args, **kwargs):
        assert kwargs == {"threshold": 0.05, "min_area_ratio": 0.001}
        return [{"region": [0.2, 0.3, 0.5, 0.6], "area_ratio": 0.09}]

    monkeypatch.setattr(
        "autofacodex.tools.validate_candidate.extract_diff_regions",
        fake_extract_diff_regions,
    )

    report = validate_candidate(task_dir, attempt=1)

    visual_issue = next(issue for issue in report.pages[0].issues if issue.type == "visual_fidelity")
    assert visual_issue.region == [0.2, 0.3, 0.5, 0.6]
    assert visual_issue.repair_hints["action"] == "adjust_bbox"
    assert visual_issue.repair_hints["diff_area_ratio"] == 0.09


def test_validate_candidate_rejects_inspection_page_count_mismatch(
    tmp_path: Path, monkeypatch
):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_task(task_dir, ppt_text="Editable Title")
    (task_dir / "reports" / "inspection.v1.json").write_text(
        json.dumps({"pages": []}), encoding="utf-8"
    )
    _stub_validation_tools(task_dir, monkeypatch)

    with pytest.raises(RuntimeError, match="Inspection page count 0 does not match extracted page count 1"):
        validate_candidate(task_dir, attempt=1)


def test_validate_candidate_rejects_slide_model_page_count_mismatch(
    tmp_path: Path, monkeypatch
):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_task(task_dir, ppt_text="Editable Title")
    model = SlideModel(
        slides=[
            {
                "page_number": 1,
                "size": {"width": 10, "height": 7.5},
                "elements": [],
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
    (task_dir / "slides" / "slide-model.v1.json").write_text(
        model.model_dump_json(indent=2), encoding="utf-8"
    )
    _stub_validation_tools(task_dir, monkeypatch)

    with pytest.raises(RuntimeError, match="Slide model page count 2 does not match extracted page count 1"):
        validate_candidate(task_dir, attempt=1)


def test_validate_candidate_rejects_slide_model_page_number_mismatch(
    tmp_path: Path, monkeypatch
):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_task(task_dir, ppt_text="Editable Title", model_page_number=2)
    _stub_validation_tools(task_dir, monkeypatch)

    with pytest.raises(
        RuntimeError,
        match="Slide model page_number 2 does not match extracted page_number 1 at index 0",
    ):
        validate_candidate(task_dir, attempt=1)
