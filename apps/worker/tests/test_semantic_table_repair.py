import json
from pathlib import Path

from autofacodex.contracts import SlideModel, ValidatorReport
from autofacodex.tools import semantic_table_repair
from autofacodex.tools.semantic_table_repair import upgrade_semantic_tables_with_guard


def _write_model(task_dir: Path) -> None:
    (task_dir / "slides").mkdir(parents=True)
    model = SlideModel(
        slides=[
            {
                "page_number": 1,
                "size": {"width": 10, "height": 7.5},
                "elements": [
                    {
                        "id": "table-1",
                        "type": "table",
                        "x": 1,
                        "y": 1,
                        "w": 5,
                        "h": 1,
                        "style": {
                            "role": "semantic_table",
                            "opacity": 0,
                            "rows": [["A", "B"], ["1", "2"]],
                        },
                    }
                ],
                "raster_fallback_regions": [],
            }
        ]
    )
    (task_dir / "slides" / "slide-model.v1.json").write_text(
        model.model_dump_json(indent=2),
        encoding="utf-8",
    )


def _write_report(task_dir: Path, attempt: int, visual_score: float) -> ValidatorReport:
    report = ValidatorReport(
        task_id=task_dir.name,
        attempt=attempt,
        aggregate_status="repair_needed",
        pages=[
            {
                "page_number": 1,
                "status": "repair_needed",
                "visual_score": visual_score,
                "editable_score": 1.0,
                "text_coverage_score": 1.0,
                "raster_fallback_ratio": 0,
                "issues": [],
            }
        ],
    )
    (task_dir / "reports").mkdir(parents=True, exist_ok=True)
    (task_dir / "reports" / f"validator.v{attempt}.json").write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return report


def test_upgrade_semantic_tables_accepts_when_visual_score_does_not_drop(
    tmp_path: Path, monkeypatch
):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_model(task_dir)
    _write_report(task_dir, attempt=1, visual_score=0.80)
    generated_models = []

    def fake_generate(model: SlideModel, output_path: Path, asset_root: Path | None = None):
        generated_models.append(model)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"pptx")
        return output_path

    def fake_validate(received_task_dir: Path, attempt: int):
        assert received_task_dir == task_dir
        assert attempt == 2
        return _write_report(task_dir, attempt=2, visual_score=0.81)

    monkeypatch.setattr(
        "autofacodex.tools.semantic_table_repair.generate_pptx",
        fake_generate,
    )
    monkeypatch.setattr(
        "autofacodex.tools.semantic_table_repair.validate_candidate",
        fake_validate,
    )

    result = upgrade_semantic_tables_with_guard(task_dir, source_attempt=1)

    assert result["status"] == "accepted"
    assert result["target_attempt"] == 2
    assert generated_models[0].slides[0].elements[0].style["role"] == "visible_table"
    assert generated_models[0].slides[0].elements[0].style["opacity"] == 1
    assert (task_dir / "slides" / "slide-model.v2.json").is_file()
    assert (task_dir / "reports" / "semantic-table-repair.v2.json").is_file()


def test_upgrade_semantic_tables_rejects_when_visual_score_drops(tmp_path: Path, monkeypatch):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_model(task_dir)
    _write_report(task_dir, attempt=1, visual_score=0.80)

    def fake_generate(model: SlideModel, output_path: Path, asset_root: Path | None = None):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"pptx")
        return output_path

    def fake_validate(received_task_dir: Path, attempt: int):
        return _write_report(task_dir, attempt=2, visual_score=0.70)

    monkeypatch.setattr(
        "autofacodex.tools.semantic_table_repair.generate_pptx",
        fake_generate,
    )
    monkeypatch.setattr(
        "autofacodex.tools.semantic_table_repair.validate_candidate",
        fake_validate,
    )

    result = upgrade_semantic_tables_with_guard(
        task_dir,
        source_attempt=1,
        min_page_visual_delta=-0.01,
    )

    assert result["status"] == "rejected"
    assert result["pages"][0]["source_visual_score"] == 0.80
    assert result["pages"][0]["target_visual_score"] == 0.70


def test_upgrade_semantic_tables_hides_covered_source_text_when_promoting(
    tmp_path: Path, monkeypatch
):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "slides").mkdir()
    model = SlideModel(
        slides=[
            {
                "page_number": 1,
                "size": {"width": 10, "height": 7.5},
                "elements": [
                    {
                        "id": "source-text-1",
                        "type": "text",
                        "text": "A",
                        "x": 1.1,
                        "y": 1.1,
                        "w": 0.2,
                        "h": 0.2,
                        "style": {"font_size": 12},
                    },
                    {
                        "id": "table-1",
                        "type": "table",
                        "x": 1,
                        "y": 1,
                        "w": 5,
                        "h": 1,
                        "style": {
                            "role": "semantic_table",
                            "opacity": 0,
                            "covered_text_ids": ["source-text-1"],
                            "rows": [["A", "B"], ["1", "2"]],
                        },
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
    _write_report(task_dir, attempt=1, visual_score=0.80)
    generated_models = []

    def fake_generate(model: SlideModel, output_path: Path, asset_root: Path | None = None):
        generated_models.append(model)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"pptx")
        return output_path

    def fake_validate(received_task_dir: Path, attempt: int):
        return _write_report(task_dir, attempt=2, visual_score=0.80)

    monkeypatch.setattr(
        "autofacodex.tools.semantic_table_repair.generate_pptx",
        fake_generate,
    )
    monkeypatch.setattr(
        "autofacodex.tools.semantic_table_repair.validate_candidate",
        fake_validate,
    )

    result = upgrade_semantic_tables_with_guard(task_dir, source_attempt=1)

    assert result["status"] == "accepted"
    source_text = generated_models[0].slides[0].elements[0]
    assert source_text.style["opacity"] == 0


def test_upgrade_semantic_tables_noops_without_semantic_table(tmp_path: Path):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "slides").mkdir()
    (task_dir / "slides" / "slide-model.v1.json").write_text(
        SlideModel(
            slides=[
                {
                    "page_number": 1,
                    "size": {"width": 10, "height": 7.5},
                    "elements": [],
                    "raster_fallback_regions": [],
                }
            ]
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    _write_report(task_dir, attempt=1, visual_score=0.80)

    result = upgrade_semantic_tables_with_guard(task_dir, source_attempt=1)

    assert result["status"] == "no_semantic_tables"
    assert not (task_dir / "slides" / "slide-model.v2.json").exists()


def test_semantic_table_repair_cli_runs_guard_and_prints_json(
    tmp_path: Path, monkeypatch, capsys
):
    task_dir = tmp_path / "task"
    task_dir.mkdir()

    def fake_upgrade(
        received_task_dir: Path,
        *,
        source_attempt: int,
        target_attempt: int | None,
        min_page_visual_delta: float,
    ):
        assert received_task_dir == task_dir
        assert source_attempt == 3
        assert target_attempt == 4
        assert min_page_visual_delta == -0.02
        return {"status": "accepted", "target_attempt": 4}

    monkeypatch.setattr(
        semantic_table_repair,
        "upgrade_semantic_tables_with_guard",
        fake_upgrade,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "semantic_table_repair",
            str(task_dir),
            "--source-attempt",
            "3",
            "--target-attempt",
            "4",
            "--min-page-visual-delta",
            "-0.02",
        ],
    )

    semantic_table_repair.main()

    assert json.loads(capsys.readouterr().out) == {
        "status": "accepted",
        "target_attempt": 4,
    }
