import math

from autofacodex.contracts import SlideElement, SlideModel, SlideSize, SlideSpec

DECK_WIDTH = 13.333
DOMINANT_BACKGROUND_MIN_AREA_RATIO = 0.7
BACKGROUND_ROLE_MIN_AREA_RATIO = 0.9
SUPPRESSED_FRAGMENT_MAX_AREA_RATIO = 0.2
SUPPRESSED_FRAGMENT_MIN_CONTAINMENT_RATIO = 0.95
MISSING_SEQNO = 1_000_000_000
HIDDEN_FOREGROUND_ROLES = {"watermark", "semantic_table"}
BackgroundFragmentKey = tuple[
    str,
    str | None,
    str | None,
    tuple[tuple[str, object], ...],
    tuple[float, ...],
]
WATERMARK_KEYWORDS = (
    "仅供",
    "内部参考",
    "内部文件",
    "资本推荐",
    "confidential",
    "draft",
    "do not distribute",
    "not for distribution",
    "internal use",
)


def _positive_float(page: dict, field: str) -> float:
    try:
        value = page[field]
    except KeyError as exc:
        raise ValueError(f"Page {page.get('page_number', '?')} is missing {field}") from exc

    try:
        dimension = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Page {page.get('page_number', '?')} {field} must be numeric and greater than 0"
        ) from exc

    if dimension <= 0:
        raise ValueError(
            f"Page {page.get('page_number', '?')} {field} must be numeric and greater than 0"
        )
    return dimension


def _bbox(value: object) -> list[float]:
    return [float(item) for item in value or []]


def _coords(bbox: list[float], page_width: float, page_height: float, size: SlideSize) -> dict:
    if len(bbox) != 4:
        raise ValueError("bbox must have four numeric values")
    x0, y0, x1, y1 = bbox
    return {
        "x": x0 * size.width / page_width,
        "y": y0 * size.height / page_height,
        "w": max(0.01, (x1 - x0) * size.width / page_width),
        "h": max(0.01, (y1 - y0) * size.height / page_height),
    }


def _area_ratio(bbox: list[float], page_width: float, page_height: float) -> float:
    if len(bbox) != 4 or page_width <= 0 or page_height <= 0:
        return 0.0
    x0, y0, x1, y1 = bbox
    area = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    return min(1.0, area / (page_width * page_height))


def _is_background_bbox(bbox: list[float], page_width: float, page_height: float) -> bool:
    return _area_ratio(bbox, page_width, page_height) >= BACKGROUND_ROLE_MIN_AREA_RATIO


def _point_coords(point: list[float], page_width: float, page_height: float, size: SlideSize) -> dict:
    if len(point) != 2:
        raise ValueError("point must have two numeric values")
    return {
        "x": point[0] * size.width / page_width,
        "y": point[1] * size.height / page_height,
    }


def _seqno(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return MISSING_SEQNO


def _opacity(value: object) -> float | None:
    if value is None:
        return None
    try:
        opacity = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, opacity))


def _is_hidden_style(style: dict) -> bool:
    if style.get("role") in HIDDEN_FOREGROUND_ROLES:
        return True
    return _opacity(style.get("opacity")) == 0


def _hex_color(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return f"#{value & 0xFFFFFF:06X}"
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        channels = [max(0, min(255, round(float(item) * 255))) for item in value[:3]]
        return f"#{channels[0]:02X}{channels[1]:02X}{channels[2]:02X}"
    return None


def _font_scale(page_width: float, size: SlideSize) -> float:
    return size.width * 72 / page_width


def _is_bold(font: str) -> bool:
    normalized = font.lower()
    return any(token in normalized for token in ("bold", "black", "heavy", "demi"))


def _is_italic(font: str) -> bool:
    normalized = font.lower()
    return any(token in normalized for token in ("italic", "oblique"))


def _text_style(span: dict, page_width: float, size: SlideSize) -> dict:
    style: dict = {}
    if span.get("size") is not None:
        style["font_size"] = float(span["size"]) * _font_scale(page_width, size)
    if span.get("font"):
        font = str(span["font"])
        style["font_family"] = font
        style["bold"] = _is_bold(font)
        style["italic"] = _is_italic(font)
    color = _hex_color(span.get("color"))
    if color:
        style["color"] = color
    return style


def _rotation_from_direction(direction: object) -> float | None:
    vector = _bbox(direction)
    if len(vector) != 2:
        return None
    dx, dy = vector
    if abs(dx) < 0.001 and abs(dy) < 0.001:
        return None
    angle = math.degrees(math.atan2(dy, dx))
    if abs(angle) < 0.5:
        return None
    return angle


def _is_watermark_text(
    text: str,
    bbox: list[float],
    page_width: float,
    page_height: float,
    rotation: float | None,
    style: dict,
) -> bool:
    normalized_text = " ".join(text.lower().split())
    compact_text = normalized_text.replace(" ", "")
    if not any(keyword in normalized_text or keyword in compact_text for keyword in WATERMARK_KEYWORDS):
        return False
    large_region = _area_ratio(bbox, page_width, page_height) >= 0.05
    large_font = float(style.get("font_size", 0) or 0) >= 24
    rotated = rotation is not None and abs(rotation) >= 10
    return rotated or large_region or large_font


def _merged_bbox(boxes: list[list[float]]) -> list[float]:
    valid_boxes = [box for box in boxes if len(box) == 4]
    if not valid_boxes:
        return []
    return [
        min(box[0] for box in valid_boxes),
        min(box[1] for box in valid_boxes),
        max(box[2] for box in valid_boxes),
        max(box[3] for box in valid_boxes),
    ]


def _line_text_element(
    page_number: int,
    element_index: int,
    block: dict,
    line: dict,
    page_width: float,
    page_height: float,
    size: SlideSize,
) -> tuple[int, int, SlideElement] | None:
    runs = []
    seqnos = []
    span_boxes = []
    for span in line.get("spans", []):
        text = str(span.get("text", ""))
        if not text.strip():
            continue
        span_boxes.append(_bbox(span.get("bbox")))
        run_style = _text_style(span, page_width, size)
        runs.append({"text": text, **run_style})
        if (seqno := _seqno(span.get("seqno"))) != MISSING_SEQNO:
            seqnos.append(seqno)

    text = "".join(str(run["text"]) for run in runs)
    if not text.strip():
        return None
    bbox = _bbox(line.get("bbox")) or _merged_bbox(span_boxes) or _bbox(block.get("bbox"))
    if len(bbox) != 4:
        return None
    style = {key: value for key, value in runs[0].items() if key != "text"}
    style["runs"] = runs
    rotation = _rotation_from_direction(line.get("dir"))
    if rotation is not None:
        style["rotation"] = rotation
    if _is_watermark_text(text, bbox, page_width, page_height, rotation, style):
        style["role"] = "watermark"
        style["opacity"] = 0
    element = SlideElement(
        id=f"p{page_number}-text-{element_index}",
        type="text",
        text=text,
        **_coords(bbox, page_width, page_height, size),
        style=style,
    )
    return (min(seqnos, default=MISSING_SEQNO), element_index, element)


def _text_elements(
    page: dict, page_width: float, page_height: float, size: SlideSize
) -> list[tuple[int, int, SlideElement]]:
    elements: list[tuple[int, int, SlideElement]] = []
    page_number = page["page_number"]
    element_index = 1
    for block in page.get("text_blocks", []):
        if block.get("type") != "text":
            continue
        for line in block.get("lines", []):
            element = _line_text_element(
                page_number, element_index, block, line, page_width, page_height, size
            )
            if element is None:
                continue
            elements.append(element)
            element_index += 1
    return elements


def _image_element(
    page_number: int,
    image_index: int,
    block: dict,
    page_width: float,
    page_height: float,
    size: SlideSize,
) -> tuple[int, int, SlideElement] | None:
    source = block.get("source")
    bbox = _bbox(block.get("bbox"))
    if not source or len(bbox) != 4:
        return None
    source = str(source)
    if source.startswith("objects/"):
        source = f"extracted/{source}"
    style = {}
    if block.get("content_hash"):
        style["content_hash"] = str(block["content_hash"])
    element = SlideElement(
        id=f"p{page_number}-image-{image_index}",
        type="image",
        source=source,
        **_coords(bbox, page_width, page_height, size),
        style=style,
    )
    return (_seqno(block.get("seqno")), image_index, element)


def _shape_element(
    page_number: int,
    shape_index: int,
    drawing: dict,
    page_width: float,
    page_height: float,
    size: SlideSize,
) -> tuple[int, int, SlideElement] | None:
    bbox = _bbox(drawing.get("bbox"))
    shape_type = drawing.get("shape")
    if shape_type not in {"rect", "line"} or len(bbox) != 4:
        return None

    style = {"shape": str(shape_type)}
    if _is_background_bbox(bbox, page_width, page_height):
        style["role"] = "background"
    if drawing.get("stroke"):
        style["line_color"] = str(drawing["stroke"])
    if shape_type == "rect" and drawing.get("fill"):
        style["fill_color"] = str(drawing["fill"])
        if (opacity := _opacity(drawing.get("fill_opacity"))) is not None:
            style["fill_opacity"] = opacity
    if drawing.get("stroke_width") is not None:
        style["line_width"] = float(drawing["stroke_width"]) * _font_scale(page_width, size)
    elif shape_type == "rect" and drawing.get("fill") and not drawing.get("stroke"):
        style["line_color"] = str(drawing["fill"])
        style["line_width"] = 0
    if (opacity := _opacity(drawing.get("stroke_opacity"))) is not None:
        style["line_opacity"] = opacity

    if shape_type == "line":
        p1 = _point_coords(_bbox(drawing.get("p1")), page_width, page_height, size)
        p2 = _point_coords(_bbox(drawing.get("p2")), page_width, page_height, size)
        style.update(
            {
                "x1": p1["x"],
                "y1": p1["y"],
                "x2": p2["x"],
                "y2": p2["y"],
            }
        )

    element = SlideElement(
        id=f"p{page_number}-shape-{shape_index}",
        type="shape",
        **_coords(bbox, page_width, page_height, size),
        style=style,
    )
    return (_seqno(drawing.get("seqno")), shape_index, element)


def _clustered(values: list[float], tolerance: float = 0.04) -> list[float]:
    if not values:
        return []
    clusters: list[list[float]] = []
    for value in sorted(values):
        if clusters and abs(value - clusters[-1][-1]) <= tolerance:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    return [sum(cluster) / len(cluster) for cluster in clusters]


def _element_bbox(element: SlideElement) -> list[float]:
    if element.type == "shape" and element.style.get("shape") == "line":
        x1 = float(element.style.get("x1", element.x))
        y1 = float(element.style.get("y1", element.y))
        x2 = float(element.style.get("x2", element.x + element.w))
        y2 = float(element.style.get("y2", element.y + element.h))
        return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
    return [element.x, element.y, element.x + element.w, element.y + element.h]


def _contains_bbox(outer: list[float], inner: list[float], tolerance: float = 0.03) -> bool:
    return (
        inner[0] >= outer[0] - tolerance
        and inner[1] >= outer[1] - tolerance
        and inner[2] <= outer[2] + tolerance
        and inner[3] <= outer[3] + tolerance
    )


def _slide_area(size: SlideSize) -> float:
    return float(size.width) * float(size.height)


def _element_area_ratio_on_slide(element: SlideElement, size: SlideSize) -> float:
    area = _slide_area(size)
    if area <= 0:
        return 0.0
    return max(0.0, min(1.0, float(element.w) * float(element.h) / area))


def _containment_ratio(outer: list[float], inner: list[float]) -> float:
    if len(outer) != 4 or len(inner) != 4:
        return 0.0
    left = max(outer[0], inner[0])
    top = max(outer[1], inner[1])
    right = min(outer[2], inner[2])
    bottom = min(outer[3], inner[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    inner_area = max(0.0, inner[2] - inner[0]) * max(0.0, inner[3] - inner[1])
    if inner_area <= 0:
        return 1.0 if _contains_bbox(outer, inner) else 0.0
    return intersection / inner_area


def _dominant_background_entry(
    positioned: list[tuple[int, int, SlideElement]],
    size: SlideSize,
) -> tuple[int, int, SlideElement] | None:
    candidates = [
        entry
        for entry in positioned
        if entry[2].type == "image"
        and _element_area_ratio_on_slide(entry[2], size) >= DOMINANT_BACKGROUND_MIN_AREA_RATIO
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda entry: _element_area_ratio_on_slide(entry[2], size))


def _is_background_fragment_candidate(
    element: SlideElement,
    dominant_background: SlideElement,
    size: SlideSize,
) -> bool:
    if element.id == dominant_background.id:
        return False
    if element.type in {"text", "table"}:
        return False
    if element.type not in {"image", "shape"}:
        return False
    if element.style.get("role") == "background":
        return False
    if _element_area_ratio_on_slide(element, size) > SUPPRESSED_FRAGMENT_MAX_AREA_RATIO:
        return False
    return (
        _containment_ratio(_element_bbox(dominant_background), _element_bbox(element))
        >= SUPPRESSED_FRAGMENT_MIN_CONTAINMENT_RATIO
    )


def _background_fragment_key(
    element: SlideElement,
) -> BackgroundFragmentKey:
    shape_type = None
    source = (
        str(element.style.get("content_hash") or element.source)
        if element.type == "image"
        else None
    )
    style_fields = (
        "fill_color",
        "fill_opacity",
        "line_color",
        "line_opacity",
        "line_width",
    )
    style_key = tuple(
        (field, element.style[field]) for field in style_fields if field in element.style
    )
    if element.type == "shape":
        shape_type = str(element.style.get("shape", ""))
        if shape_type == "line":
            endpoints = sorted(
                (
                    (
                        float(element.style.get("x1", element.x)),
                        float(element.style.get("y1", element.y)),
                    ),
                    (
                        float(element.style.get("x2", element.x + element.w)),
                        float(element.style.get("y2", element.y + element.h)),
                    ),
                )
            )
            geometry = tuple(round(value, 4) for point in endpoints for value in point)
            return (element.type, shape_type, source, style_key, geometry)
    return (
        element.type,
        shape_type,
        source,
        style_key,
        tuple(round(value, 4) for value in _element_bbox(element)),
    )


def _duplicate_background_fragment_keys(
    positioned: list[tuple[int, int, SlideElement]],
    dominant_background: SlideElement,
    size: SlideSize,
) -> set[BackgroundFragmentKey]:
    fragment_counts: dict[BackgroundFragmentKey, int] = {}
    for _seq, _index, element in positioned:
        if not _is_background_fragment_candidate(element, dominant_background, size):
            continue
        key = _background_fragment_key(element)
        fragment_counts[key] = fragment_counts.get(key, 0) + 1
    return {key for key, count in fragment_counts.items() if count > 1}


def _has_editable_foreground(
    positioned: list[tuple[int, int, SlideElement]],
    dominant_entry: tuple[int, int, SlideElement],
) -> bool:
    dominant_seq, dominant_index, dominant_background = dominant_entry

    def is_visible_foreground(element: SlideElement) -> bool:
        if element.id == dominant_background.id:
            return False
        if _is_hidden_style(element.style):
            return False
        if element.type == "text":
            return bool((element.text or "").strip())
        if element.type == "table":
            rows = element.style.get("rows", [])
            if not isinstance(rows, list):
                return False
            return any(str(cell or "").strip() for row in rows for cell in row)
        return False

    return any(
        (seq, index) > (dominant_seq, dominant_index) and is_visible_foreground(element)
        for seq, index, element in positioned
    )


def _apply_dominant_background_strategy(
    positioned: list[tuple[int, int, SlideElement]],
    size: SlideSize,
) -> list[tuple[int, int, SlideElement]]:
    dominant_entry = _dominant_background_entry(positioned, size)
    if dominant_entry is None:
        return positioned

    dominant = dominant_entry[2]
    duplicate_fragment_keys = _duplicate_background_fragment_keys(positioned, dominant, size)
    dominant_area_ratio = _element_area_ratio_on_slide(dominant, size)
    has_editable_foreground = _has_editable_foreground(positioned, dominant_entry)
    if (
        dominant_area_ratio >= BACKGROUND_ROLE_MIN_AREA_RATIO
        and has_editable_foreground
    ):
        dominant.style = {**dominant.style, "role": "background"}
    if not duplicate_fragment_keys:
        return positioned

    if (
        dominant_area_ratio >= DOMINANT_BACKGROUND_MIN_AREA_RATIO
        and has_editable_foreground
    ):
        dominant.style = {**dominant.style, "role": "background"}
    kept: list[tuple[int, int, SlideElement]] = []
    kept_fragment_keys: set[BackgroundFragmentKey] = set()
    for entry in sorted(positioned, key=lambda item: (item[0], item[1])):
        element = entry[2]
        if _is_background_fragment_candidate(element, dominant, size):
            key = _background_fragment_key(element)
            if key in duplicate_fragment_keys:
                if key in kept_fragment_keys:
                    continue
                kept_fragment_keys.add(key)
        kept.append(entry)
    return kept


def _center_in_bbox(element: SlideElement, bbox: list[float]) -> bool:
    cx = element.x + element.w / 2
    cy = element.y + element.h / 2
    return bbox[0] <= cx <= bbox[2] and bbox[1] <= cy <= bbox[3]


def _text_cell(
    text_entries: list[tuple[int, int, SlideElement]],
    x_bounds: list[float],
    y_bounds: list[float],
) -> tuple[list[list[str]], list[SlideElement]]:
    rows = [["" for _ in range(len(x_bounds) - 1)] for _ in range(len(y_bounds) - 1)]
    consumed: list[SlideElement] = []
    cell_texts: dict[tuple[int, int], list[SlideElement]] = {}
    table_bbox = [x_bounds[0], y_bounds[0], x_bounds[-1], y_bounds[-1]]

    for _seq, _index, element in text_entries:
        if not _center_in_bbox(element, table_bbox):
            continue
        cx = element.x + element.w / 2
        cy = element.y + element.h / 2
        row_index = next(
            (index for index in range(len(y_bounds) - 1) if y_bounds[index] <= cy <= y_bounds[index + 1]),
            None,
        )
        col_index = next(
            (index for index in range(len(x_bounds) - 1) if x_bounds[index] <= cx <= x_bounds[index + 1]),
            None,
        )
        if row_index is None or col_index is None:
            continue
        cell_bbox = [
            x_bounds[col_index],
            y_bounds[row_index],
            x_bounds[col_index + 1],
            y_bounds[row_index + 1],
        ]
        if not _contains_bbox(cell_bbox, _element_bbox(element), tolerance=0.08):
            continue
        cell_texts.setdefault((row_index, col_index), []).append(element)
        consumed.append(element)

    for (row_index, col_index), elements in cell_texts.items():
        elements.sort(key=lambda element: (element.y, element.x))
        rows[row_index][col_index] = "\n".join(element.text or "" for element in elements)
    return rows, consumed


def _looks_like_table(rows: list[list[str]]) -> bool:
    nonempty_rows = [sum(1 for cell in row if cell.strip()) for row in rows]
    total_cells = len(rows) * len(rows[0]) if rows else 0
    nonempty_cells = sum(nonempty_rows)
    density = nonempty_cells / total_cells if total_cells else 0.0
    return (
        len(rows) >= 3
        and len(rows[0]) >= 2
        and sum(count >= 2 for count in nonempty_rows) >= 2
        and density >= 0.45
    )


def _line_coordinates(element: SlideElement) -> tuple[str, float, float, float] | None:
    if element.type != "shape" or element.style.get("shape") != "line":
        return None
    x1 = float(element.style.get("x1", element.x))
    y1 = float(element.style.get("y1", element.y))
    x2 = float(element.style.get("x2", element.x + element.w))
    y2 = float(element.style.get("y2", element.y + element.h))
    if abs(y1 - y2) <= 0.03 and abs(x2 - x1) >= 0.5:
        return ("horizontal", y1, min(x1, x2), max(x1, x2))
    if abs(x1 - x2) <= 0.03 and abs(y2 - y1) >= 0.3:
        return ("vertical", x1, min(y1, y2), max(y1, y2))
    return None


def _table_candidate(
    page_number: int,
    table_index: int,
    positioned: list[tuple[int, int, SlideElement]],
) -> tuple[tuple[int, int, SlideElement], set[str]] | None:
    text_entries = [entry for entry in positioned if entry[2].type == "text"]
    shape_entries = [
        entry
        for entry in positioned
        if entry[2].type == "shape" and entry[2].style.get("role") != "background"
    ]
    horizontal_lines = []
    vertical_lines = []
    rects = []
    for entry in shape_entries:
        element = entry[2]
        if element.style.get("shape") == "rect":
            rects.append(entry)
            continue
        coordinates = _line_coordinates(element)
        if coordinates is None:
            continue
        if coordinates[0] == "horizontal":
            horizontal_lines.append((entry, coordinates))
        elif coordinates[0] == "vertical":
            vertical_lines.append((entry, coordinates))

    if len(horizontal_lines) < 2:
        return None

    left = min(line[1][2] for line in horizontal_lines)
    right = max(line[1][3] for line in horizontal_lines)
    y_values = [line[1][1] for line in horizontal_lines]
    first_horizontal = min(y_values)
    last_horizontal = max(y_values)
    nearby_rects = [
        entry
        for entry in rects
        if _element_bbox(entry[2])[2] >= left - 0.1
        and _element_bbox(entry[2])[0] <= right + 0.1
        and _element_bbox(entry[2])[3] >= first_horizontal - 0.08
        and _element_bbox(entry[2])[1] <= last_horizontal + 0.08
    ]
    if nearby_rects:
        y_values.extend(_element_bbox(entry[2])[1] for entry in nearby_rects)
    top = min(y_values)
    bottom = max(y_values)

    x_bounds = [left, right]
    x_bounds.extend(line[1][1] for line in vertical_lines if line[1][2] <= bottom and line[1][3] >= top)
    for entry in nearby_rects:
        bbox = _element_bbox(entry[2])
        x_bounds.extend([bbox[0], bbox[2]])
    y_bounds = [top, bottom]
    y_bounds.extend(line[1][1] for line in horizontal_lines)
    for entry in nearby_rects:
        bbox = _element_bbox(entry[2])
        y_bounds.extend([bbox[1], bbox[3]])

    x_bounds = _clustered([value for value in x_bounds if left - 0.2 <= value <= right + 0.2])
    y_bounds = _clustered(y_bounds)
    if len(x_bounds) < 3 or len(y_bounds) < 3:
        return None

    rows, consumed_text = _text_cell(text_entries, x_bounds, y_bounds)
    if not _looks_like_table(rows):
        return None

    table_bbox = [x_bounds[0], y_bounds[0], x_bounds[-1], y_bounds[-1]]
    covered_ids: set[str] = set()
    base_text_style = next((element.style for element in consumed_text if element.style), {})
    table_style = {
        key: value
        for key, value in base_text_style.items()
        if key in {"font_size", "font_family", "color", "bold", "italic"}
    }
    table_style.setdefault("font_size", 12)
    table_style["rows"] = rows
    table_style["col_widths"] = [
        x_bounds[index + 1] - x_bounds[index] for index in range(len(x_bounds) - 1)
    ]
    table_style["row_heights"] = [
        y_bounds[index + 1] - y_bounds[index] for index in range(len(y_bounds) - 1)
    ]
    table_style["covered_text_ids"] = [element.id for element in consumed_text]
    table_style["role"] = "semantic_table"
    table_style["opacity"] = 0
    table = SlideElement(
        id=f"p{page_number}-table-{table_index}",
        type="table",
        x=table_bbox[0],
        y=table_bbox[1],
        w=table_bbox[2] - table_bbox[0],
        h=table_bbox[3] - table_bbox[1],
        style=table_style,
    )
    sequence = min(
        [entry[0] for entry in positioned if entry[2].id in covered_ids],
        default=MISSING_SEQNO,
    )
    insertion_index = max((entry[1] for entry in positioned), default=0) + table_index
    return ((sequence, insertion_index, table), covered_ids)


def _collapse_table_regions(
    page_number: int,
    positioned: list[tuple[int, int, SlideElement]],
) -> list[tuple[int, int, SlideElement]]:
    candidate = _table_candidate(page_number, 1, positioned)
    if candidate is None:
        return positioned
    table_entry, covered_ids = candidate
    return [entry for entry in positioned if entry[2].id not in covered_ids] + [table_entry]


def _positioned_elements(
    page: dict, page_width: float, page_height: float, size: SlideSize
) -> list[SlideElement]:
    positioned: list[tuple[int, int, SlideElement]] = []
    insertion_index = 0

    shape_index = 1
    for drawing in page.get("drawings", []):
        shape = _shape_element(
            page["page_number"], shape_index, drawing, page_width, page_height, size
        )
        if shape is not None:
            positioned.append((shape[0], insertion_index, shape[2]))
            insertion_index += 1
            shape_index += 1

    for text in _text_elements(page, page_width, page_height, size):
        positioned.append((text[0], insertion_index, text[2]))
        insertion_index += 1

    image_index = 1
    for block in page.get("text_blocks", []):
        if block.get("type") != "image":
            continue
        image = _image_element(
            page["page_number"], image_index, block, page_width, page_height, size
        )
        if image is not None:
            positioned.append((image[0], insertion_index, image[2]))
            insertion_index += 1
            image_index += 1

    positioned = _collapse_table_regions(page["page_number"], positioned)
    positioned = _apply_dominant_background_strategy(positioned, size)
    positioned.sort(key=lambda item: (item[0], item[1]))
    return [element for _seq, _index, element in positioned]


def _fallback_text_element(page: dict, size: SlideSize) -> SlideElement | None:
    text = page.get("text", "").strip()
    if not text:
        return None
    return SlideElement(
        id=f"p{page['page_number']}-text-1",
        type="text",
        text=text,
        x=0.5,
        y=0.5,
        w=size.width - 1,
        h=max(1.0, size.height - 1),
        style={"font_size": 14},
    )


def build_initial_slide_model(extracted: dict) -> SlideModel:
    slides: list[SlideSpec] = []
    pages = extracted["pages"]
    page_dimensions = [
        (_positive_float(page, "width"), _positive_float(page, "height")) for page in pages
    ]
    if not pages:
        return SlideModel(slides=slides)

    first_width, first_height = page_dimensions[0]
    deck_size = SlideSize(width=DECK_WIDTH, height=DECK_WIDTH * first_height / first_width)

    for page, (page_width, page_height) in zip(pages, page_dimensions, strict=True):
        elements = _positioned_elements(page, page_width, page_height, deck_size)
        if not elements and (fallback := _fallback_text_element(page, deck_size)):
            elements.append(fallback)
        slides.append(
            SlideSpec(
                page_number=page["page_number"],
                size=deck_size,
                elements=elements,
                raster_fallback_regions=[],
            )
        )
    return SlideModel(slides=slides)
