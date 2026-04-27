import math
from pathlib import Path

import fitz


def render_pdf_pages(pdf_path: Path, output_dir: Path, zoom: float = 2.0) -> list[Path]:
    if not math.isfinite(zoom) or zoom <= 0 or zoom > 8.0:
        raise ValueError("zoom must be finite and greater than 0 up to 8.0")

    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    try:
        paths: list[Path] = []
        matrix = fitz.Matrix(zoom, zoom)
        for index, page in enumerate(doc, start=1):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            output = output_dir / f"page-{index:03d}.png"
            pixmap.save(output)
            paths.append(output)
        return paths
    finally:
        doc.close()
