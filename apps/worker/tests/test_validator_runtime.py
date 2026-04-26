from pathlib import Path

from autofacodex.agents.validator_runtime import build_validator_report


def test_build_validator_report_fails_full_page_raster(tmp_path: Path):
    report = build_validator_report(
        task_id="task_1",
        attempt=1,
        page_count=1,
        visual_scores={1: 0.98},
        editable_scores={1: 0.1},
        text_scores={1: 0.0},
        raster_ratios={1: 0.95},
    )

    page = report.pages[0]
    assert page.status == "repair_needed"
    assert page.issues[0].type == "editability"
