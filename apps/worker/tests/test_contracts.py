import pytest
from pydantic import ValidationError

from autofacodex.contracts import TaskManifest, SlideModel, ValidatorReport


def test_task_manifest_paths_are_task_relative():
    manifest = TaskManifest(
        task_id="task_123",
        workflow_type="pdf_to_ppt",
        input_pdf="input.pdf",
        attempt=1,
        max_attempts=3,
    )

    assert manifest.workflow_type == "pdf_to_ppt"
    assert manifest.input_pdf == "input.pdf"


def test_task_manifest_rejects_unknown_extra_field():
    with pytest.raises(ValidationError):
        TaskManifest(
            task_id="task_123",
            workflow_type="pdf_to_ppt",
            input_pdf="input.pdf",
            attempt=1,
            max_attempts=3,
            unexpected="extra",
        )


def test_slide_model_accepts_empty_editable_elements_and_fallbacks():
    model = SlideModel(
        slides=[
            {
                "page_number": 1,
                "size": {"width": 13.333, "height": 7.5},
                "elements": [],
                "raster_fallback_regions": [],
            }
        ]
    )

    assert model.slides[0].page_number == 1


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (0, 1),
        (-1, 1),
        (1, 0),
        (1, -1),
    ],
)
def test_slide_model_rejects_non_positive_fallback_region_size(width: float, height: float):
    with pytest.raises(ValidationError):
        SlideModel(
            slides=[
                {
                    "page_number": 1,
                    "size": {"width": 13.333, "height": 7.5},
                    "elements": [],
                    "raster_fallback_regions": [
                        {
                            "x": 0,
                            "y": 0,
                            "w": width,
                            "h": height,
                            "reason": "image-only region",
                        }
                    ],
                }
            ]
        )


def test_slide_model_uses_isolated_mutable_defaults():
    first = SlideModel(slides=[{"page_number": 1, "size": {"width": 13.333, "height": 7.5}}])
    second = SlideModel(slides=[{"page_number": 2, "size": {"width": 13.333, "height": 7.5}}])

    first.slides[0].elements.append(
        {
            "id": "text_1",
            "type": "text",
            "x": 0,
            "y": 0,
            "w": 1,
            "h": 1,
        }
    )

    assert second.slides[0].elements == []


def test_validator_report_requires_page_status():
    report = ValidatorReport(
        task_id="task_123",
        attempt=1,
        pages=[
            {
                "page_number": 1,
                "status": "repair_needed",
                "visual_score": 0.75,
                "editable_score": 0.4,
                "text_coverage_score": 0.9,
                "raster_fallback_ratio": 0.6,
                "issues": [
                    {
                        "type": "editability",
                        "message": "Large raster region detected",
                        "suggested_action": "Reconstruct visible text as editable text boxes",
                    }
                ],
            }
        ],
    )

    assert report.pages[0].status == "repair_needed"


@pytest.mark.parametrize(
    "page_update",
    [
        {"status": "unknown"},
        {"visual_score": 1.1},
        {"editable_score": -0.1},
        {"text_coverage_score": 1.1},
        {"raster_fallback_ratio": -0.1},
    ],
)
def test_validator_report_rejects_invalid_status_or_score(page_update: dict):
    page = {
        "page_number": 1,
        "status": "repair_needed",
        "visual_score": 0.75,
        "editable_score": 0.4,
        "text_coverage_score": 0.9,
        "raster_fallback_ratio": 0.6,
        "issues": [],
    }
    page.update(page_update)

    with pytest.raises(ValidationError):
        ValidatorReport(task_id="task_123", attempt=1, pages=[page])


@pytest.mark.parametrize("region", [[0, 0, 1], [0, 0, 1, 1, 2]])
def test_validator_report_rejects_bad_issue_region_length(region: list[float]):
    with pytest.raises(ValidationError):
        ValidatorReport(
            task_id="task_123",
            attempt=1,
            pages=[
                {
                    "page_number": 1,
                    "status": "repair_needed",
                    "visual_score": 0.75,
                    "editable_score": 0.4,
                    "text_coverage_score": 0.9,
                    "raster_fallback_ratio": 0.6,
                    "issues": [
                        {
                            "type": "editability",
                            "message": "Large raster region detected",
                            "suggested_action": "Reconstruct visible text as editable text boxes",
                            "region": region,
                        }
                    ],
                }
            ],
        )


def test_validator_report_accepts_page_and_issue_evidence_paths():
    report = ValidatorReport(
        task_id="task_123",
        attempt=1,
        pages=[
            {
                "page_number": 1,
                "status": "repair_needed",
                "visual_score": 0.75,
                "editable_score": 0.4,
                "text_coverage_score": 0.9,
                "raster_fallback_ratio": 0.6,
                "evidence_paths": {
                    "pdf_render": "renders/pdf/page-001.png",
                    "ppt_render": "output/rendered-pages-v1/page-001.png",
                    "diff": "output/diagnostics-v1/page-001-diff.png",
                    "inspection": "reports/inspection.v1.json",
                    "text_coverage": "reports/text-coverage.v1.json",
                },
                "issues": [
                    {
                        "type": "editability",
                        "message": "Large raster region detected",
                        "suggested_action": "Reconstruct visible text as editable text boxes",
                        "evidence_paths": ["reports/inspection.v1.json"],
                    }
                ],
            }
        ],
    )

    page = report.pages[0]
    assert page.evidence_paths["diff"] == "output/diagnostics-v1/page-001-diff.png"
    assert page.issues[0].evidence_paths == ["reports/inspection.v1.json"]


def test_validator_report_accepts_aggregate_status():
    report = ValidatorReport(
        task_id="task_123",
        attempt=1,
        aggregate_status="repair_needed",
        pages=[
            {
                "page_number": 1,
                "status": "repair_needed",
                "visual_score": 0.75,
                "editable_score": 0.4,
                "text_coverage_score": 0.9,
                "raster_fallback_ratio": 0.6,
                "issues": [],
            }
        ],
    )

    assert report.aggregate_status == "repair_needed"
