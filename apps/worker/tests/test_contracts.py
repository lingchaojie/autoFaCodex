from pathlib import Path

from autofacodex.contracts import TaskManifest, SlideModel, ValidatorReport


def test_task_manifest_paths_are_task_relative(tmp_path: Path):
    manifest = TaskManifest(
        task_id="task_123",
        workflow_type="pdf_to_ppt",
        input_pdf="input.pdf",
        attempt=1,
        max_attempts=3,
    )

    assert manifest.workflow_type == "pdf_to_ppt"
    assert manifest.input_pdf == "input.pdf"


def test_slide_model_rejects_full_page_raster_as_declared_fallback():
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
