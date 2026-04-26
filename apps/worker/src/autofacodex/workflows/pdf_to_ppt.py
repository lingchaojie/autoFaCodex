from pathlib import Path

from autofacodex.agents.validator_runtime import build_validator_report
from autofacodex.tools.pdf_extract import extract_pdf
from autofacodex.tools.pdf_render import render_pdf_pages
from autofacodex.tools.pptx_generate import generate_pptx
from autofacodex.tools.pptx_inspect import inspect_pptx_editability
from autofacodex.tools.slide_model_builder import build_initial_slide_model


WORKFLOW_DIRS = [
    "extracted",
    "renders/pdf",
    "renders/ppt",
    "renders/diff",
    "slides",
    "output",
    "reports",
    "logs",
]


def _validate_pdf_renders(render_paths: list[Path], expected_count: int) -> None:
    if len(render_paths) != expected_count:
        raise RuntimeError(f"Expected {expected_count} PDF renders, got {len(render_paths)}")

    missing_paths = [path for path in render_paths if not path.exists()]
    if missing_paths:
        missing = ", ".join(str(path) for path in missing_paths)
        raise RuntimeError(f"PDF render does not exist: {missing}")


def run_pdf_to_ppt(task_dir: Path) -> None:
    for directory in WORKFLOW_DIRS:
        (task_dir / directory).mkdir(parents=True, exist_ok=True)

    (task_dir / "logs" / "workflow.log").write_text(
        "pdf_to_ppt workflow started\n", encoding="utf-8"
    )

    pdf_path = task_dir / "input.pdf"
    extracted = extract_pdf(pdf_path, task_dir / "extracted")
    page_count = len(extracted["pages"])
    pdf_renders = render_pdf_pages(pdf_path, task_dir / "renders" / "pdf")
    _validate_pdf_renders(pdf_renders, page_count)

    slide_model = build_initial_slide_model(extracted)
    (task_dir / "slides" / "slide-model.v1.json").write_text(
        slide_model.model_dump_json(indent=2), encoding="utf-8"
    )

    candidate = generate_pptx(slide_model, task_dir / "output" / "candidate.v1.pptx")
    inspection = inspect_pptx_editability(candidate)
    page_numbers = range(1, page_count + 1)
    editable_scores = {
        index: 1.0 if page.get("text_runs", 0) > 0 else 0.0
        for index, page in enumerate(inspection["pages"], start=1)
    }
    report = build_validator_report(
        task_id=task_dir.name,
        attempt=1,
        page_count=page_count,
        visual_scores={page_number: 0.5 for page_number in page_numbers},
        editable_scores=editable_scores,
        text_scores={page_number: 0.8 for page_number in range(1, page_count + 1)},
        raster_ratios={page_number: 0.0 for page_number in range(1, page_count + 1)},
    )
    (task_dir / "reports" / "validator.v1.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
