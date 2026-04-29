from typing import Any


def _slide_for_page(model: dict[str, Any], page_number: int) -> dict[str, Any] | None:
    for slide in model.get("slides", []):
        if slide.get("page_number") == page_number:
            return slide
    return None


def _normalized_bbox(
    element: dict[str, Any],
    slide: dict[str, Any],
) -> tuple[float, float, float, float]:
    size = slide.get("size") or {}
    width = float(size.get("width") or 1)
    height = float(size.get("height") or 1)
    x1 = float(element.get("x") or 0) / width
    y1 = float(element.get("y") or 0) / height
    x2 = (float(element.get("x") or 0) + float(element.get("w") or 0)) / width
    y2 = (float(element.get("y") or 0) + float(element.get("h") or 0)) / height
    return x1, y1, x2, y2


def _overlap_ratio(a: list[float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    b_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return 0.0 if b_area <= 0 else intersection / b_area


def apply_repair_action(
    model: dict[str, Any],
    *,
    page_number: int,
    action: dict[str, Any],
) -> dict[str, Any]:
    slide = _slide_for_page(model, page_number)
    if slide is None:
        return {"status": "noop", "changed_element_ids": [], "reason": "page_not_found"}

    action_name = action.get("action")
    if action_name != "mark_region_background":
        return {"status": "noop", "changed_element_ids": [], "reason": "unsupported_action"}

    region = action.get("region") or [0, 0, 0, 0]
    min_overlap_ratio = float(action.get("min_overlap_ratio", 0.2))
    changed: list[str] = []
    for element in slide.get("elements", []):
        if element.get("type") != "image":
            continue
        if _overlap_ratio(region, _normalized_bbox(element, slide)) < min_overlap_ratio:
            continue
        style = dict(element.get("style") or {})
        style["role"] = "background"
        element["style"] = style
        changed.append(str(element.get("id")))

    return {
        "status": "changed" if changed else "noop",
        "changed_element_ids": changed,
        "action": action_name,
    }
