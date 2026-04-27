import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


SLIDE_XML_RE = re.compile(r"^ppt/slides/slide\d+\.xml$")
NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
EMU_PER_INCH = 914400


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _slide_number(slide_name: str) -> int:
    return int(slide_name.removeprefix("ppt/slides/slide").removesuffix(".xml"))


def _emu(value: str | None) -> float:
    return float(value or 0) / EMU_PER_INCH


def _presentation_size(archive: ZipFile) -> tuple[float, float]:
    if "ppt/presentation.xml" not in archive.namelist():
        return (10.0, 7.5)
    root = ET.fromstring(archive.read("ppt/presentation.xml"))
    size = root.find(".//p:sldSz", NS)
    if size is None:
        return (10.0, 7.5)
    return (_emu(size.attrib.get("cx")), _emu(size.attrib.get("cy")))


def _geometry(node: ET.Element) -> dict[str, float]:
    off = node.find(".//a:xfrm/a:off", NS)
    ext = node.find(".//a:xfrm/a:ext", NS)
    return {
        "x": _emu(off.attrib.get("x") if off is not None else None),
        "y": _emu(off.attrib.get("y") if off is not None else None),
        "w": _emu(ext.attrib.get("cx") if ext is not None else None),
        "h": _emu(ext.attrib.get("cy") if ext is not None else None),
    }


def _area_ratio(geometry: dict[str, float], slide_width: float, slide_height: float) -> float:
    slide_area = slide_width * slide_height
    if slide_area <= 0:
        return 0.0
    return max(0.0, min(1.0, geometry["w"] * geometry["h"] / slide_area))


def _clipped_rect(
    geometry: dict[str, float], slide_width: float, slide_height: float
) -> tuple[float, float, float, float] | None:
    x1 = max(0.0, geometry["x"])
    y1 = max(0.0, geometry["y"])
    x2 = min(slide_width, geometry["x"] + geometry["w"])
    y2 = min(slide_height, geometry["y"] + geometry["h"])
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)


def _union_area(rects: list[tuple[float, float, float, float]]) -> float:
    if not rects:
        return 0.0
    x_points = sorted({point for rect in rects for point in (rect[0], rect[2])})
    area = 0.0
    for left, right in zip(x_points, x_points[1:], strict=False):
        if right <= left:
            continue
        y_intervals = [
            (top, bottom)
            for x1, top, x2, bottom in rects
            if x1 < right and x2 > left
        ]
        if not y_intervals:
            continue
        y_intervals.sort()
        covered_y = 0.0
        current_top, current_bottom = y_intervals[0]
        for top, bottom in y_intervals[1:]:
            if top <= current_bottom:
                current_bottom = max(current_bottom, bottom)
            else:
                covered_y += current_bottom - current_top
                current_top, current_bottom = top, bottom
        covered_y += current_bottom - current_top
        area += (right - left) * covered_y
    return area


def _coverage_ratio(
    geometries: list[dict[str, float]], slide_width: float, slide_height: float
) -> float:
    slide_area = slide_width * slide_height
    if slide_area <= 0:
        return 0.0
    rects = [
        rect
        for geometry in geometries
        if (rect := _clipped_rect(geometry, slide_width, slide_height)) is not None
    ]
    return max(0.0, min(1.0, _union_area(rects) / slide_area))


def inspect_pptx_editability(pptx_path: Path) -> dict:
    with ZipFile(pptx_path) as archive:
        slide_width, slide_height = _presentation_size(archive)
        slide_names = sorted(
            (name for name in archive.namelist() if SLIDE_XML_RE.fullmatch(name)),
            key=_slide_number,
        )
        pages = []
        for slide_name in slide_names:
            root = ET.fromstring(archive.read(slide_name))
            nodes = list(root.iter())
            pictures = [_geometry(node) for node in root.findall(".//p:pic", NS)]
            shapes = [_geometry(node) for node in root.findall(".//p:sp", NS)]
            text_runs = [node.text or "" for node in root.findall(".//a:t", NS)]
            picture_area_ratios = [
                _area_ratio(geometry, slide_width, slide_height) for geometry in pictures
            ]
            largest_picture_area_ratio = max(picture_area_ratios, default=0.0)
            total_picture_area_ratio = min(1.0, sum(picture_area_ratios))
            picture_coverage_ratio = _coverage_ratio(pictures, slide_width, slide_height)
            pages.append(
                {
                    "slide": slide_name,
                    "size": {"width": slide_width, "height": slide_height},
                    "text_runs": sum(1 for node in nodes if _localname(node.tag) == "t"),
                    "pictures": sum(1 for node in nodes if _localname(node.tag) == "pic"),
                    "shapes": sum(1 for node in nodes if _localname(node.tag) == "sp"),
                    "tables": sum(1 for node in nodes if _localname(node.tag) == "tbl"),
                    "text": "".join(text_runs),
                    "picture_geometries": pictures,
                    "shape_geometries": shapes,
                    "largest_picture_area_ratio": largest_picture_area_ratio,
                    "total_picture_area_ratio": total_picture_area_ratio,
                    "picture_coverage_ratio": picture_coverage_ratio,
                    "has_full_page_picture": (
                        largest_picture_area_ratio >= 0.92
                        or picture_coverage_ratio >= 0.92
                    ),
                }
            )
    return {"pages": pages}
