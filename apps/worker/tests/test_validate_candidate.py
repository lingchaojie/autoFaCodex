import json
from pathlib import Path

from PIL import Image

from autofacodex.contracts import SlideModel, ValidatorReport
from autofacodex.tools.validate_candidate import validate_candidate


def _write_task(task_dir: Path, *, ppt_text: str, full_page_picture: bool = False) -> None:
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
                "page_number": 1,
                "size": {"width": 10, "height": 7.5},
                "elements": [],
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


def test_validate_candidate_passes_high_quality_editable_page(tmp_path: Path, monkeypatch):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_task(task_dir, ppt_text="Editable Title")
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

    report = validate_candidate(task_dir, attempt=1)

    assert report.aggregate_status == "pass"
    assert report.pages[0].status == "pass"
    assert report.pages[0].visual_score == 0.96
    assert report.pages[0].text_coverage_score == 1.0
    assert (task_dir / "reports" / "validator.v1.json").is_file()
    ValidatorReport.model_validate_json(
        (task_dir / "reports" / "validator.v1.json").read_text(encoding="utf-8")
    )


def test_validate_candidate_rejects_full_page_picture(tmp_path: Path, monkeypatch):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_task(task_dir, ppt_text="Editable Title", full_page_picture=True)
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

    report = validate_candidate(task_dir, attempt=1)

    assert report.aggregate_status == "repair_needed"
    assert report.pages[0].status == "repair_needed"
    assert any(issue.type == "editability" for issue in report.pages[0].issues)
