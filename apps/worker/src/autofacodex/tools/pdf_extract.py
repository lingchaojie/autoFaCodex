import json
from pathlib import Path

import fitz


def extract_pdf(pdf_path: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    pages = []
    for index, page in enumerate(doc, start=1):
        text_dict = page.get_text("dict")
        images = page.get_images(full=True)
        drawings = page.get_drawings()
        pages.append(
            {
                "page_number": index,
                "width": page.rect.width,
                "height": page.rect.height,
                "text": page.get_text("text"),
                "text_blocks": text_dict.get("blocks", []),
                "image_count": len(images),
                "drawing_count": len(drawings),
            }
        )
    result = {"pages": pages}
    (output_dir / "pages.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
