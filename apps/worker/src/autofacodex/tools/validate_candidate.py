import json
from pathlib import Path
from typing import Literal

from autofacodex.contracts import PageValidation, SlideModel, ValidatorIssue, ValidatorReport
from autofacodex.tools.pptx_inspect import inspect_pptx_editability
from autofacodex.tools.pptx_render import render_pptx_pages
from autofacodex.tools.text_coverage import compare_text_coverage
from autofacodex.tools.visual_diff import compare_images, write_compare_image, write_diff_image


PageStatus = Literal["pass", "repair_needed", "manual_review", "failed"]


def _candidate_path(task_dir: Path, attempt: int) -> Path:
    return task_dir / "output" / f"candidate.v{attempt}.pptx"


def _slide_model_path(task_dir: Path, attempt: int) -> Path:
    return task_dir / "slides" / f"slide-model.v{attempt}.json"


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _clamp_ratio(value: float) -> float:
    return max(0.0, min(1.0, value))


def _raster_ratio(model: SlideModel, page_index: int) -> float:
    if page_index < 0 or page_index >= len(model.slides):
        return 1.0
    slide = model.slides[page_index]
    slide_area = slide.size.width * slide.size.height
    if slide_area <= 0:
        return 1.0
    raster_area = sum(region.w * region.h for region in slide.raster_fallback_regions)
    return _clamp_ratio(raster_area / slide_area)


def _ratio_value(value: object) -> float:
    try:
        return _clamp_ratio(float(value))
    except (TypeError, ValueError):
        return 0.0


def _inspection_picture_ratio(inspection_page: dict) -> float:
    return max(
        _ratio_value(inspection_page.get("largest_picture_area_ratio")),
        _ratio_value(inspection_page.get("total_picture_area_ratio")),
        _ratio_value(inspection_page.get("picture_coverage_ratio")),
    )


def _editable_score(inspection_page: dict) -> float:
    if inspection_page.get("has_full_page_picture", False):
        return 0.0
    editable_objects = (
        int(inspection_page.get("text_runs", 0) or 0)
        + int(inspection_page.get("shapes", 0) or 0)
        + int(inspection_page.get("tables", 0) or 0)
    )
    return 1.0 if editable_objects > 0 else 0.0


def _status_from_scores(
    *,
    full_page_picture: bool,
    raster_ratio: float,
    editable_score: float,
    visual_score: float,
    text_score: float,
) -> PageStatus:
    if full_page_picture or raster_ratio >= 0.5 or editable_score < 0.5:
        return "repair_needed"
    if visual_score < 0.85 or text_score < 0.8:
        return "repair_needed"
    if visual_score < 0.9:
        return "manual_review"
    return "pass"


def _issues(
    *,
    full_page_picture: bool,
    raster_ratio: float,
    editable_score: float,
    visual_score: float,
    text_score: float,
    evidence_paths: dict[str, str],
) -> list[ValidatorIssue]:
    issues: list[ValidatorIssue] = []
    if full_page_picture or raster_ratio >= 0.5 or editable_score < 0.5:
        issues.append(
            ValidatorIssue(
                type="editability",
                message="Slide contains excessive raster content or too few editable elements",
                suggested_action="Reconstruct visible text and simple shapes as editable PPT elements",
                evidence_paths=[evidence_paths["inspection"]],
            )
        )
    if visual_score < 0.9:
        issues.append(
            ValidatorIssue(
                type="visual_fidelity",
                message="Rendered PPTX differs from the source PDF page",
                suggested_action="Use the diff render to adjust positions, sizes, colors, and missing regions",
                evidence_paths=[evidence_paths["diff"], evidence_paths["compare"]],
            )
        )
    if text_score < 0.8:
        issues.append(
            ValidatorIssue(
                type="text_coverage",
                message="Editable PPTX text does not cover source PDF text",
                suggested_action="Recover missing text as editable text boxes",
                evidence_paths=[evidence_paths["text_coverage"], evidence_paths["inspection"]],
            )
        )
    return issues


def _aggregate_status(pages: list[PageValidation]) -> PageStatus:
    priority = {"failed": 3, "repair_needed": 2, "manual_review": 1, "pass": 0}
    if not pages:
        return "failed"
    return max((page.status for page in pages), key=lambda status: priority[status])


def _load_pages(task_dir: Path) -> list[dict]:
    extracted = json.loads((task_dir / "extracted" / "pages.json").read_text(encoding="utf-8"))
    pages = extracted.get("pages", [])
    if not isinstance(pages, list):
        raise RuntimeError("extracted/pages.json must contain a pages list")
    return pages


def _pdf_render_paths(task_dir: Path) -> list[Path]:
    return sorted((task_dir / "renders" / "pdf").glob("page-*.png"))


def _validate_slide_model_alignment(slide_model: SlideModel, extracted_pages: list[dict]) -> None:
    if len(slide_model.slides) != len(extracted_pages):
        raise RuntimeError(
            f"Slide model page count {len(slide_model.slides)} does not match "
            f"extracted page count {len(extracted_pages)}"
        )
    for index, extracted_page in enumerate(extracted_pages):
        expected_page_number = int(extracted_page.get("page_number", index + 1))
        model_page_number = slide_model.slides[index].page_number
        if model_page_number != expected_page_number:
            raise RuntimeError(
                f"Slide model page_number {model_page_number} does not match "
                f"extracted page_number {expected_page_number} at index {index}"
            )


def validate_candidate(task_dir: Path, attempt: int = 1) -> ValidatorReport:
    candidate = _candidate_path(task_dir, attempt)
    if not candidate.is_file():
        raise FileNotFoundError(candidate)

    slide_model = SlideModel.model_validate_json(
        _slide_model_path(task_dir, attempt).read_text(encoding="utf-8")
    )
    extracted_pages = _load_pages(task_dir)
    page_count = len(extracted_pages)
    _validate_slide_model_alignment(slide_model, extracted_pages)

    pdf_renders = _pdf_render_paths(task_dir)
    if len(pdf_renders) != page_count:
        raise RuntimeError(
            f"PDF render count {len(pdf_renders)} does not match extracted page count {page_count}"
        )

    render_result = render_pptx_pages(candidate, task_dir / "output" / f"ppt-render-v{attempt}")
    ppt_renders = list(render_result.page_images)
    if len(ppt_renders) != page_count:
        raise RuntimeError(
            f"PPT render count {len(ppt_renders)} does not match extracted page count {page_count}"
        )

    reports_dir = task_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_dir = task_dir / "output" / f"diagnostics-v{attempt}"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)

    inspection = inspect_pptx_editability(candidate)
    inspection_path = reports_dir / f"inspection.v{attempt}.json"
    inspection_path.write_text(json.dumps(inspection, indent=2), encoding="utf-8")
    inspection_pages = inspection.get("pages", [])
    if not isinstance(inspection_pages, list):
        raise RuntimeError("Inspection pages must be a list")
    if len(inspection_pages) != page_count:
        raise RuntimeError(
            f"Inspection page count {len(inspection_pages)} does not match "
            f"extracted page count {page_count}"
        )

    text_coverage_pages = []
    validations: list[PageValidation] = []
    text_coverage_path = reports_dir / f"text-coverage.v{attempt}.json"

    for page_index, extracted_page in enumerate(extracted_pages):
        page_number = int(extracted_page.get("page_number", page_index + 1))
        pdf_render = pdf_renders[page_index]
        ppt_render = ppt_renders[page_index]
        diff_path = diagnostics_dir / f"page-{page_number:03d}-diff.png"
        compare_path = diagnostics_dir / f"page-{page_number:03d}-compare.png"

        write_diff_image(pdf_render, ppt_render, diff_path)
        write_compare_image(pdf_render, ppt_render, compare_path)
        visual_score = compare_images(pdf_render, ppt_render)

        inspection_page = (
            inspection_pages[page_index]
            if page_index < len(inspection_pages) and isinstance(inspection_pages[page_index], dict)
            else {}
        )
        source_text = str(extracted_page.get("text") or "")
        candidate_text = str(inspection_page.get("text") or "")
        text_coverage = compare_text_coverage(source_text, candidate_text)
        text_coverage_pages.append({"page_number": page_number, **text_coverage})
        text_score = float(text_coverage["score"])

        full_page_picture = bool(inspection_page.get("has_full_page_picture", False))
        raster_ratio = max(
            _raster_ratio(slide_model, page_index),
            _inspection_picture_ratio(inspection_page),
        )
        editable_score = _editable_score(inspection_page)
        evidence_paths = {
            "pdf_render": _relative_path(pdf_render, task_dir),
            "ppt_render": _relative_path(ppt_render, task_dir),
            "diff": _relative_path(diff_path, task_dir),
            "compare": _relative_path(compare_path, task_dir),
            "inspection": _relative_path(inspection_path, task_dir),
            "text_coverage": _relative_path(text_coverage_path, task_dir),
        }

        status = _status_from_scores(
            full_page_picture=full_page_picture,
            raster_ratio=raster_ratio,
            editable_score=editable_score,
            visual_score=visual_score,
            text_score=text_score,
        )
        validations.append(
            PageValidation(
                page_number=page_number,
                status=status,
                visual_score=visual_score,
                editable_score=editable_score,
                text_coverage_score=text_score,
                raster_fallback_ratio=raster_ratio,
                issues=_issues(
                    full_page_picture=full_page_picture,
                    raster_ratio=raster_ratio,
                    editable_score=editable_score,
                    visual_score=visual_score,
                    text_score=text_score,
                    evidence_paths=evidence_paths,
                ),
                evidence_paths=evidence_paths,
            )
        )

    text_coverage_path.write_text(json.dumps(text_coverage_pages, indent=2), encoding="utf-8")

    report = ValidatorReport(
        task_id=task_dir.name,
        attempt=attempt,
        pages=validations,
        aggregate_status=_aggregate_status(validations),
    )
    (reports_dir / f"validator.v{attempt}.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    return report
