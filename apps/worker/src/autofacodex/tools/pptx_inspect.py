from pathlib import Path
from zipfile import ZipFile


def inspect_pptx_editability(pptx_path: Path) -> dict:
    with ZipFile(pptx_path) as archive:
        slide_names = sorted(
            name
            for name in archive.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )
        pages = []
        for slide_name in slide_names:
            xml = archive.read(slide_name).decode("utf-8", errors="ignore")
            pages.append(
                {
                    "slide": slide_name,
                    "text_runs": xml.count("<a:t>"),
                    "pictures": xml.count("<p:pic>"),
                    "shapes": xml.count("<p:sp>"),
                }
            )
    return {"pages": pages}
