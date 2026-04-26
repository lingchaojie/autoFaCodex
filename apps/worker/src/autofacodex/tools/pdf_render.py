from pathlib import Path

import fitz


def render_pdf_pages(pdf_path: Path, output_dir: Path, zoom: float = 2.0) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    paths: list[Path] = []
    matrix = fitz.Matrix(zoom, zoom)
    for index, page in enumerate(doc, start=1):
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        output = output_dir / f"page-{index:03d}.png"
        pixmap.save(output)
        paths.append(output)
    return paths
