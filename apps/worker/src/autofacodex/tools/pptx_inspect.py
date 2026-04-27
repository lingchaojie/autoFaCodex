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
    return max(0.0, geometry["w"] * geometry["h"] / slide_area)


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
                    "has_full_page_picture": largest_picture_area_ratio >= 0.92,
                }
            )
    return {"pages": pages}
