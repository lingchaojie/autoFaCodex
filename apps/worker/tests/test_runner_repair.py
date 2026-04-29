from pathlib import Path

from autofacodex.contracts import SlideModel, ValidatorReport
from autofacodex.tools.runner_repair import run_deterministic_runner_repair


def _write_repair_task(task_dir: Path) -> None:
    (task_dir / "slides").mkdir(parents=True)
    (task_dir / "reports").mkdir(parents=True)
    (task_dir / "output").mkdir(parents=True)
    (task_dir / "extracted").mkdir(parents=True)

    model = SlideModel(
        slides=[
            {
                "page_number": 1,
                "size": {"width": 10, "height": 7.5},
                "elements": [
                    {
                        "id": "background-candidate",
                        "type": "image",
                        "x": 0,
                        "y": 0.5,
                        "w": 10,
                        "h": 6.5,
                        "source": "extracted/objects/images/page-001-image-001.png",
                    },
                    {
                        "id": "foreground-title",
                        "type": "text",
                        "x": 1,
                        "y": 1,
                        "w": 4,
                        "h": 0.5,
                        "text": "Editable title",
                    },
                ],
                "raster_fallback_regions": [],
            }
        ]
    )
    (task_dir / "slides" / "slide-model.v1.json").write_text(
        model.model_dump_json(indent=2),
        encoding="utf-8",
    )

    report = ValidatorReport(
        task_id=task_dir.name,
        attempt=1,
        aggregate_status="repair_needed",
        pages=[
            {
                "page_number": 1,
                "status": "repair_needed",
                "visual_score": 0.88,
                "editable_score": 1.0,
                "text_coverage_score": 1.0,
                "raster_fallback_ratio": 0.86,
                "issues": [
                    {
                        "type": "editability",
                        "message": "Slide contains excessive raster content",
                        "suggested_action": "Reconstruct visible text and simple shapes",
                    }
                ],
            }
        ],
    )
    (task_dir / "reports" / "validator.v1.json").write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )


def test_deterministic_runner_repair_marks_large_images_as_background(
    tmp_path: Path, monkeypatch
):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    _write_repair_task(task_dir)

    def fake_generate_pptx(_model, output_path: Path, *, asset_root: Path | None = None):
        assert asset_root == task_dir
        output_path.write_bytes(b"pptx")
        return output_path

    monkeypatch.setattr(
        "autofacodex.tools.runner_repair.generate_pptx",
        fake_generate_pptx,
    )

    result = run_deterministic_runner_repair(
        task_dir,
        source_attempt=1,
        target_attempt=2,
        reason="runner_timeout",
        max_pages=2,
    )

    repaired = SlideModel.model_validate_json(
        (task_dir / "slides" / "slide-model.v2.json").read_text(encoding="utf-8")
    )
    image = repaired.slides[0].elements[0]
    assert image.id == "background-candidate"
    assert image.style["role"] == "background"
    assert (task_dir / "output" / "candidate.v2.pptx").is_file()
    assert (task_dir / "reports" / "runner-repair.v2.json").is_file()
    assert result["mode"] == "deterministic_fallback"
    assert result["changed_pages"] == [1]


def test_deterministic_runner_repair_marks_grouped_images_as_background(
    tmp_path: Path, monkeypatch
):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    _write_repair_task(task_dir)
    model = SlideModel.model_validate_json(
        (task_dir / "slides" / "slide-model.v1.json").read_text(encoding="utf-8")
    )
    data = model.model_dump()
    data["slides"][0]["elements"] = [
        {
            "id": "background-left",
            "type": "image",
            "x": 0,
            "y": 1,
            "w": 4,
            "h": 6,
            "source": "extracted/objects/images/page-001-image-001.png",
        },
        {
            "id": "background-right",
            "type": "image",
            "x": 4,
            "y": 1,
            "w": 4,
            "h": 6,
            "source": "extracted/objects/images/page-001-image-002.png",
        },
        {
            "id": "foreground-title",
            "type": "text",
            "x": 1,
            "y": 1,
            "w": 4,
            "h": 0.5,
            "text": "Editable title",
        },
    ]
    (task_dir / "slides" / "slide-model.v1.json").write_text(
        SlideModel.model_validate(data).model_dump_json(indent=2),
        encoding="utf-8",
    )

    def fake_generate_pptx(_model, output_path: Path, *, asset_root: Path | None = None):
        output_path.write_bytes(b"pptx")
        return output_path

    monkeypatch.setattr(
        "autofacodex.tools.runner_repair.generate_pptx",
        fake_generate_pptx,
    )

    result = run_deterministic_runner_repair(
        task_dir,
        source_attempt=1,
        target_attempt=2,
        reason="runner_timeout",
    )

    repaired = SlideModel.model_validate_json(
        (task_dir / "slides" / "slide-model.v2.json").read_text(encoding="utf-8")
    )
    styles = {element.id: element.style for element in repaired.slides[0].elements}
    assert styles["background-left"]["role"] == "background"
    assert styles["background-right"]["role"] == "background"
    assert result["changed_pages"] == [1]


def test_deterministic_runner_repair_uses_validator_region_hints(
    tmp_path: Path, monkeypatch
):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    _write_repair_task(task_dir)
    report = ValidatorReport.model_validate_json(
        (task_dir / "reports" / "validator.v1.json").read_text(encoding="utf-8")
    )
    data = report.model_dump()
    data["pages"][0]["issues"].append(
        {
            "type": "visual_fidelity",
            "message": "Localized visual mismatch",
            "suggested_action": "adjust_bbox",
            "region": [0.0, 0.0, 1.0, 1.0],
            "repair_hints": {
                "action": "mark_region_background",
                "region": [0.0, 0.0, 1.0, 1.0],
                "min_overlap_ratio": 0.2,
            },
        }
    )
    (task_dir / "reports" / "validator.v1.json").write_text(
        ValidatorReport.model_validate(data).model_dump_json(indent=2),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "autofacodex.tools.runner_repair.generate_pptx",
        lambda _model, output_path, *, asset_root=None: output_path.write_bytes(b"pptx")
        or output_path,
    )

    result = run_deterministic_runner_repair(
        task_dir,
        source_attempt=1,
        target_attempt=2,
        reason="region_hint",
    )

    assert any(action["type"] == "validator_repair_hint" for action in result["actions"])
