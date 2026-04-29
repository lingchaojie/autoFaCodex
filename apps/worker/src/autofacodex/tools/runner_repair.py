import argparse
import json
from pathlib import Path
from typing import Any

from autofacodex.contracts import SlideModel, ValidatorReport
from autofacodex.tools.pptx_generate import generate_pptx
from autofacodex.tools.repair_actions import apply_repair_action


def _slide_model_path(task_dir: Path, attempt: int) -> Path:
    return task_dir / "slides" / f"slide-model.v{attempt}.json"


def _candidate_path(task_dir: Path, attempt: int) -> Path:
    return task_dir / "output" / f"candidate.v{attempt}.pptx"


def _runner_report_path(task_dir: Path, attempt: int) -> Path:
    return task_dir / "reports" / f"runner-repair.v{attempt}.json"


def _validator_report_path(task_dir: Path, attempt: int) -> Path:
    return task_dir / "reports" / f"validator.v{attempt}.json"


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _element_area_ratio(element: dict[str, Any], slide: dict[str, Any]) -> float:
    size = slide.get("size") or {}
    slide_area = float(size.get("width") or 0) * float(size.get("height") or 0)
    if slide_area <= 0:
        return 0.0
    return max(
        0.0,
        min(
            1.0,
            (float(element.get("w") or 0) * float(element.get("h") or 0))
            / slide_area,
        ),
    )


def _opacity(value: object) -> float | None:
    if value is None:
        return None
    try:
        opacity = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, opacity))


def _is_visible_foreground_element(element: dict[str, Any]) -> bool:
    style = element.get("style") or {}
    if style.get("role") in {"watermark", "semantic_table"}:
        return False
    if _opacity(style.get("opacity")) == 0:
        return False
    if element.get("type") == "text":
        return bool(str(element.get("text") or "").strip())
    if element.get("type") == "table":
        rows = style.get("rows", [])
        if not isinstance(rows, list):
            return False
        return any(str(cell or "").strip() for row in rows for cell in row)
    return False


def _has_visible_foreground_after(slide: dict[str, Any], element_index: int) -> bool:
    return any(
        index > element_index and _is_visible_foreground_element(element)
        for index, element in enumerate(slide.get("elements", []))
    )


def _page_is_safe_background_repair_candidate(page: Any) -> bool:
    if page.status not in {"repair_needed", "manual_review"}:
        return False
    if page.text_coverage_score < 0.95 or page.editable_score < 0.5:
        return False
    if page.raster_fallback_ratio < 0.5:
        return False
    return any(issue.type == "editability" for issue in page.issues)


def _repair_large_background_images(
    slide: dict[str, Any],
    *,
    page_number: int,
    min_area_ratio: float,
    min_group_member_area_ratio: float,
    target_group_area_ratio: float,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []

    image_candidates = [
        (index, element, _element_area_ratio(element, slide))
        for index, element in enumerate(slide.get("elements", []))
        if element.get("type") == "image"
    ]

    def mark_background(element: dict[str, Any], area_ratio: float, action_type: str) -> None:
        style = dict(element.get("style") or {})
        if style.get("role") == "background":
            return
        style["role"] = "background"
        element["style"] = style
        actions.append(
            {
                "type": action_type,
                "page_number": page_number,
                "element_id": element.get("id"),
                "area_ratio": area_ratio,
            }
        )

    for index, element, area_ratio in image_candidates:
        if area_ratio >= min_area_ratio and _has_visible_foreground_after(slide, index):
            mark_background(element, area_ratio, "mark_background_image")

    marked_area_ratio = sum(action["area_ratio"] for action in actions)
    grouped_candidates = sorted(
        [
            (index, element, area_ratio)
            for index, element, area_ratio in image_candidates
            if area_ratio >= min_group_member_area_ratio
            and _has_visible_foreground_after(slide, index)
        ],
        key=lambda item: item[2],
        reverse=True,
    )
    if marked_area_ratio < target_group_area_ratio:
        for _index, element, area_ratio in grouped_candidates:
            style = dict(element.get("style") or {})
            if style.get("role") == "background":
                continue
            mark_background(element, area_ratio, "mark_background_image_group")
            marked_area_ratio += area_ratio
            if marked_area_ratio >= target_group_area_ratio:
                break
    return actions


def run_deterministic_runner_repair(
    task_dir: Path,
    *,
    source_attempt: int,
    target_attempt: int,
    reason: str,
    max_pages: int | None = None,
    min_background_area_ratio: float = 0.5,
    min_group_member_area_ratio: float = 0.05,
    target_group_area_ratio: float = 0.7,
) -> dict[str, Any]:
    source_model = SlideModel.model_validate_json(
        _slide_model_path(task_dir, source_attempt).read_text(encoding="utf-8")
    )
    source_report = ValidatorReport.model_validate_json(
        _validator_report_path(task_dir, source_attempt).read_text(encoding="utf-8")
    )

    model_data = source_model.model_dump()
    pages_by_number = {slide["page_number"]: slide for slide in model_data["slides"]}
    candidate_pages = [
        page
        for page in source_report.pages
        if _page_is_safe_background_repair_candidate(page)
    ]
    if max_pages is not None:
        candidate_pages = candidate_pages[:max_pages]

    actions: list[dict[str, Any]] = []
    for page in candidate_pages:
        slide = pages_by_number.get(page.page_number)
        if slide is None:
            continue
        for issue in page.issues:
            if not issue.repair_hints:
                continue
            result = apply_repair_action(
                model_data,
                page_number=page.page_number,
                action=issue.repair_hints,
            )
            changed_element_ids = result["changed_element_ids"]
            if changed_element_ids:
                actions.append(
                    {
                        "type": "validator_repair_hint",
                        "page_number": page.page_number,
                        "issue_type": issue.type,
                        "repair_action": issue.repair_hints.get("action"),
                        "changed_element_ids": changed_element_ids,
                    }
                )
        actions.extend(
            _repair_large_background_images(
                slide,
                page_number=page.page_number,
                min_area_ratio=min_background_area_ratio,
                min_group_member_area_ratio=min_group_member_area_ratio,
                target_group_area_ratio=target_group_area_ratio,
            )
        )

    repaired_model = SlideModel.model_validate(model_data)
    target_model_path = _slide_model_path(task_dir, target_attempt)
    target_candidate_path = _candidate_path(task_dir, target_attempt)
    target_report_path = _runner_report_path(task_dir, target_attempt)
    target_model_path.parent.mkdir(parents=True, exist_ok=True)
    target_candidate_path.parent.mkdir(parents=True, exist_ok=True)
    target_report_path.parent.mkdir(parents=True, exist_ok=True)

    target_model_path.write_text(
        repaired_model.model_dump_json(indent=2),
        encoding="utf-8",
    )
    generate_pptx(repaired_model, target_candidate_path, asset_root=task_dir)

    changed_pages = sorted({int(action["page_number"]) for action in actions})
    report = {
        "task_id": task_dir.name,
        "mode": "deterministic_fallback",
        "reason": reason,
        "source_attempt": source_attempt,
        "target_attempt": target_attempt,
        "changed_pages": changed_pages,
        "actions": actions,
        "files_written": [
            _relative_path(target_model_path, task_dir),
            _relative_path(target_candidate_path, task_dir),
            _relative_path(target_report_path, task_dir),
        ],
        "remaining_risks": []
        if actions
        else ["No safe deterministic semantic repair was identified; copied the source slide model."],
    }
    target_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a bounded deterministic fallback repair for a PDF-to-PPT task."
    )
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--source-attempt", type=int, required=True)
    parser.add_argument("--target-attempt", type=int, required=True)
    parser.add_argument("--reason", default="manual")
    parser.add_argument("--max-pages", type=int)
    args = parser.parse_args()

    result = run_deterministic_runner_repair(
        args.task_dir,
        source_attempt=args.source_attempt,
        target_attempt=args.target_attempt,
        reason=args.reason,
        max_pages=args.max_pages,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
