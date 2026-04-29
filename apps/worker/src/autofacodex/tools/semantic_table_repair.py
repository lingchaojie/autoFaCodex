import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from autofacodex.contracts import SlideElement, SlideModel, ValidatorReport
from autofacodex.tools.pptx_generate import generate_pptx
from autofacodex.tools.validate_candidate import validate_candidate


def _slide_model_path(task_dir: Path, attempt: int) -> Path:
    return task_dir / "slides" / f"slide-model.v{attempt}.json"


def _candidate_path(task_dir: Path, attempt: int) -> Path:
    return task_dir / "output" / f"candidate.v{attempt}.pptx"


def _validator_report_path(task_dir: Path, attempt: int) -> Path:
    return task_dir / "reports" / f"validator.v{attempt}.json"


def _repair_report_path(task_dir: Path, attempt: int) -> Path:
    return task_dir / "reports" / f"semantic-table-repair.v{attempt}.json"


def _load_model(task_dir: Path, attempt: int) -> SlideModel:
    return SlideModel.model_validate_json(
        _slide_model_path(task_dir, attempt).read_text(encoding="utf-8")
    )


def _load_report(task_dir: Path, attempt: int) -> ValidatorReport:
    return ValidatorReport.model_validate_json(
        _validator_report_path(task_dir, attempt).read_text(encoding="utf-8")
    )


def _semantic_table_pages(model: SlideModel) -> set[int]:
    pages = set()
    for slide in model.slides:
        if any(_is_semantic_table(element) for element in slide.elements):
            pages.add(slide.page_number)
    return pages


def _is_semantic_table(element: SlideElement) -> bool:
    return element.type == "table" and element.style.get("role") == "semantic_table"


def _visible_table_model(model: SlideModel) -> SlideModel:
    data = deepcopy(model.model_dump())
    for slide in data["slides"]:
        covered_text_ids: set[str] = set()
        for element in slide["elements"]:
            style = element.get("style", {})
            if element.get("type") == "table" and style.get("role") == "semantic_table":
                style["role"] = "visible_table"
                style["opacity"] = 1
                covered_text_ids.update(
                    str(element_id)
                    for element_id in style.get("covered_text_ids", [])
                    if element_id
                )
        for element in slide["elements"]:
            if element.get("type") == "text" and element.get("id") in covered_text_ids:
                element.setdefault("style", {})["opacity"] = 0
    return SlideModel.model_validate(data)


def _page_by_number(report: ValidatorReport) -> dict[int, Any]:
    return {page.page_number: page for page in report.pages}


def _page_score_summary(
    source_report: ValidatorReport, target_report: ValidatorReport, page_numbers: set[int]
) -> list[dict[str, float | int]]:
    source_pages = _page_by_number(source_report)
    target_pages = _page_by_number(target_report)
    pages = []
    for page_number in sorted(page_numbers):
        source_page = source_pages[page_number]
        target_page = target_pages[page_number]
        pages.append(
            {
                "page_number": page_number,
                "source_visual_score": source_page.visual_score,
                "target_visual_score": target_page.visual_score,
                "delta_visual_score": target_page.visual_score - source_page.visual_score,
            }
        )
    return pages


def _write_repair_report(task_dir: Path, attempt: int, report: dict) -> None:
    path = _repair_report_path(task_dir, attempt)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def upgrade_semantic_tables_with_guard(
    task_dir: Path,
    *,
    source_attempt: int,
    target_attempt: int | None = None,
    min_page_visual_delta: float = -0.005,
) -> dict:
    target_attempt = target_attempt or source_attempt + 1
    source_model = _load_model(task_dir, source_attempt)
    page_numbers = _semantic_table_pages(source_model)
    if not page_numbers:
        return {
            "status": "no_semantic_tables",
            "source_attempt": source_attempt,
            "target_attempt": target_attempt,
            "pages": [],
        }

    source_report = _load_report(task_dir, source_attempt)
    target_model = _visible_table_model(source_model)
    _slide_model_path(task_dir, target_attempt).write_text(
        target_model.model_dump_json(indent=2),
        encoding="utf-8",
    )
    generate_pptx(
        target_model,
        _candidate_path(task_dir, target_attempt),
        asset_root=task_dir,
    )
    target_report = validate_candidate(task_dir, attempt=target_attempt)
    pages = _page_score_summary(source_report, target_report, page_numbers)
    accepted = all(
        page["delta_visual_score"] >= min_page_visual_delta for page in pages
    )
    repair_report = {
        "status": "accepted" if accepted else "rejected",
        "source_attempt": source_attempt,
        "target_attempt": target_attempt,
        "min_page_visual_delta": min_page_visual_delta,
        "pages": pages,
        "source_slide_model": f"slides/slide-model.v{source_attempt}.json",
        "target_slide_model": f"slides/slide-model.v{target_attempt}.json",
        "target_pptx": f"output/candidate.v{target_attempt}.pptx",
        "target_validator_report": f"reports/validator.v{target_attempt}.json",
    }
    _write_repair_report(task_dir, target_attempt, repair_report)
    return repair_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Try promoting semantic table overlays to visible editable PPT tables "
            "and accept only when page visual scores do not regress too far."
        )
    )
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--source-attempt", type=int, default=1)
    parser.add_argument("--target-attempt", type=int)
    parser.add_argument("--min-page-visual-delta", type=float, default=-0.005)
    args = parser.parse_args()

    result = upgrade_semantic_tables_with_guard(
        args.task_dir,
        source_attempt=args.source_attempt,
        target_attempt=args.target_attempt,
        min_page_visual_delta=args.min_page_visual_delta,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
