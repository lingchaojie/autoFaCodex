from pathlib import Path
from typing import Any

from autofacodex.tools.pptx_inspect import inspect_pptx_editability


STRATEGIES = (
    "background_plus_foreground_text",
    "fragmented_objects",
    "mostly_editable",
    "unknown",
)


def _number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _count(page: dict[str, Any], field: str) -> int:
    try:
        return int(page.get(field, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _area_ratio(geometry: dict[str, Any], size: dict[str, Any]) -> float:
    width = _number(size.get("width"))
    height = _number(size.get("height"))
    if width <= 0 or height <= 0:
        return 0.0
    return max(
        0.0,
        min(1.0, _number(geometry.get("w")) * _number(geometry.get("h")) / (width * height)),
    )


def classify_slide_strategy(page: dict[str, Any]) -> str:
    text_boxes = _count(page, "text_box_count")
    pictures = _count(page, "pictures")
    shapes = _count(page, "shapes")
    coverage = _number(page.get("picture_coverage_ratio"))
    largest_picture = _number(page.get("largest_picture_area_ratio"))

    if not any((text_boxes, pictures, shapes, coverage, largest_picture)):
        return "unknown"
    if (pictures >= 10 or shapes >= 30) and largest_picture < 0.9:
        return "fragmented_objects"
    if coverage >= 0.82 and text_boxes >= 1:
        return "background_plus_foreground_text"
    if coverage <= 0.35 and text_boxes >= 2:
        return "mostly_editable"
    return "unknown"


def _dominant_background_candidates(page: dict[str, Any]) -> list[dict[str, Any]]:
    size = page.get("size") if isinstance(page.get("size"), dict) else {}
    candidates = []
    for geometry in page.get("picture_geometries", []):
        if not isinstance(geometry, dict):
            continue
        area_ratio = _area_ratio(geometry, size)
        if area_ratio >= 0.7:
            candidates.append({**geometry, "area_ratio": round(area_ratio, 6)})
    return sorted(candidates, key=lambda item: item["area_ratio"], reverse=True)


def profile_pptx_strategy_from_inspection(inspection: dict[str, Any]) -> dict[str, Any]:
    pages = []
    strategy_counts = {strategy: 0 for strategy in STRATEGIES}
    for index, page in enumerate(inspection.get("pages", []), start=1):
        strategy = classify_slide_strategy(page)
        strategy_counts[strategy] += 1
        pages.append(
            {
                "page_number": index,
                "slide": page.get("slide"),
                "size": page.get("size", {}),
                "strategy": strategy,
                "text_runs": _count(page, "text_runs"),
                "text_box_count": _count(page, "text_box_count"),
                "pictures": _count(page, "pictures"),
                "shapes": _count(page, "shapes"),
                "tables": _count(page, "tables"),
                "largest_picture_area_ratio": round(
                    _number(page.get("largest_picture_area_ratio")), 6
                ),
                "total_picture_area_ratio": round(
                    _number(page.get("total_picture_area_ratio")), 6
                ),
                "picture_coverage_ratio": round(
                    _number(page.get("picture_coverage_ratio")), 6
                ),
                "dominant_background_candidates": _dominant_background_candidates(page),
                "picture_geometries": page.get("picture_geometries", []),
                "shape_geometries": page.get("shape_geometries", []),
                "text_box_geometries": page.get("text_box_geometries", []),
            }
        )
    return {"pages": pages, "strategy_counts": strategy_counts}


def profile_pptx_strategy(pptx_path: Path) -> dict[str, Any]:
    return profile_pptx_strategy_from_inspection(inspect_pptx_editability(pptx_path))
