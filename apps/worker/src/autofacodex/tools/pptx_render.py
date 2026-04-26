import subprocess
from pathlib import Path


def render_pptx_to_pdf(pptx_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "libreoffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(pptx_path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    output_pdf = output_dir / f"{pptx_path.stem}.pdf"
    if not output_pdf.is_file():
        raise FileNotFoundError(
            f"LibreOffice did not create expected PDF {output_pdf}. "
            f"stdout: {result.stdout or ''} stderr: {result.stderr or ''}"
        )
    return output_pdf
