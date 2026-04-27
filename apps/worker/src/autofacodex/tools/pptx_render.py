from dataclasses import dataclass
import os
import subprocess
from pathlib import Path
import uuid

from autofacodex.tools.pdf_render import render_pdf_pages


@dataclass(frozen=True)
class PptxRenderResult:
    output_pdf: Path
    page_images: list[Path]


class PptxRenderError(RuntimeError):
    pass


def _profile_dir(profile_root: Path | None, output_dir: Path, pptx_path: Path) -> Path:
    root = profile_root if profile_root is not None else output_dir / ".libreoffice"
    return root / f"profile-{pptx_path.stem}-{uuid.uuid4().hex}"


def render_pptx_to_pdf(
    pptx_path: Path,
    output_dir: Path,
    profile_root: Path | None = None,
    libreoffice_bin: str = "libreoffice",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = _profile_dir(profile_root, output_dir, pptx_path)
    profile_dir.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "HOME": str(profile_dir / "home"),
        "XDG_RUNTIME_DIR": str(profile_dir / "runtime"),
    }
    Path(env["HOME"]).mkdir(parents=True, exist_ok=True)
    Path(env["XDG_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(env["XDG_RUNTIME_DIR"]).chmod(0o700)
    result = subprocess.run(
        [
            libreoffice_bin,
            "--headless",
            "--convert-to",
            "pdf",
            f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
            "--outdir",
            str(output_dir),
            str(pptx_path),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    output_pdf = output_dir / f"{pptx_path.stem}.pdf"
    if result.returncode != 0:
        raise PptxRenderError(
            f"LibreOffice failed to render {pptx_path} to {output_pdf}. "
            f"returncode={result.returncode} stdout={result.stdout or ''} stderr={result.stderr or ''}"
        )
    if not output_pdf.is_file():
        raise FileNotFoundError(
            f"LibreOffice did not create expected PDF {output_pdf}. "
            f"returncode={result.returncode} stdout={result.stdout or ''} stderr={result.stderr or ''}"
        )
    return output_pdf


def render_pptx_pages(
    pptx_path: Path,
    output_dir: Path,
    zoom: float = 2.0,
    profile_root: Path | None = None,
    libreoffice_bin: str = "libreoffice",
) -> PptxRenderResult:
    rendered_pdf_dir = output_dir / "rendered-pdf"
    rendered_pages_dir = output_dir / "rendered-pages"
    output_pdf = render_pptx_to_pdf(
        pptx_path,
        rendered_pdf_dir,
        profile_root=profile_root,
        libreoffice_bin=libreoffice_bin,
    )
    page_images = render_pdf_pages(output_pdf, rendered_pages_dir, zoom=zoom)
    return PptxRenderResult(output_pdf=output_pdf, page_images=page_images)
