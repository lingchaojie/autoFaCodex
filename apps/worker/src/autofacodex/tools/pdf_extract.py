import json
from pathlib import Path

import fitz


def _bbox(value: object) -> list[float]:
    return [float(item) for item in value or []]


def _point(value: object) -> list[float]:
    return [float(item) for item in value or []]


def _span_metadata(span: dict) -> dict:
    return {
        "text": span.get("text", ""),
        "bbox": _bbox(span.get("bbox")),
        "origin": _point(span.get("origin")),
        "font": span.get("font"),
        "size": span.get("size"),
        "flags": span.get("flags"),
        "color": span.get("color"),
    }


def _text_block_metadata(block: dict) -> dict:
    return {
        "type": "text",
        "bbox": _bbox(block.get("bbox")),
        "lines": [
            {
                "bbox": _bbox(line.get("bbox")),
                "wmode": line.get("wmode"),
                "dir": _point(line.get("dir")),
                "spans": [_span_metadata(span) for span in line.get("spans", [])],
            }
            for line in block.get("lines", [])
        ],
    }


def _image_block_metadata(block: dict, image_xrefs: list[int]) -> dict:
    metadata = {
        "type": "image",
        "bbox": _bbox(block.get("bbox")),
        "width": block.get("width"),
        "height": block.get("height"),
        "ext": block.get("ext"),
        "colorspace": block.get("colorspace"),
        "xres": block.get("xres"),
        "yres": block.get("yres"),
        "bpc": block.get("bpc"),
        "xref": image_xrefs.pop(0) if image_xrefs else block.get("xref"),
    }
    return {key: value for key, value in metadata.items() if value is not None}


def _block_metadata(block: dict, image_xrefs: list[int]) -> dict:
    if block.get("type") == 0:
        return _text_block_metadata(block)
    if block.get("type") == 1:
        return _image_block_metadata(block, image_xrefs)
    return {
        "type": block.get("type"),
        "bbox": _bbox(block.get("bbox")),
    }


def extract_pdf(pdf_path: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    try:
        pages = []
        for index, page in enumerate(doc, start=1):
            text_dict = page.get_text("dict")
            images = page.get_images(full=True)
            image_xrefs = [image[0] for image in images]
            drawings = page.get_drawings()
            pages.append(
                {
                    "page_number": index,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "text": page.get_text("text"),
                    "text_blocks": [
                        _block_metadata(block, image_xrefs)
                        for block in text_dict.get("blocks", [])
                    ],
                    "image_count": len(images),
                    "drawing_count": len(drawings),
                }
            )
        result = {"pages": pages}
        (output_dir / "pages.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        return result
    finally:
        doc.close()
