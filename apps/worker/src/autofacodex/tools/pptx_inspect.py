import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


SLIDE_XML_RE = re.compile(r"^ppt/slides/slide\d+\.xml$")


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _slide_number(slide_name: str) -> int:
    return int(slide_name.removeprefix("ppt/slides/slide").removesuffix(".xml"))


def inspect_pptx_editability(pptx_path: Path) -> dict:
    with ZipFile(pptx_path) as archive:
        slide_names = sorted(
            (name for name in archive.namelist() if SLIDE_XML_RE.fullmatch(name)),
            key=_slide_number,
        )
        pages = []
        for slide_name in slide_names:
            root = ET.fromstring(archive.read(slide_name))
            nodes = list(root.iter())
            pages.append(
                {
                    "slide": slide_name,
                    "text_runs": sum(1 for node in nodes if _localname(node.tag) == "t"),
                    "pictures": sum(1 for node in nodes if _localname(node.tag) == "pic"),
                    "shapes": sum(1 for node in nodes if _localname(node.tag) == "sp"),
                }
            )
    return {"pages": pages}
