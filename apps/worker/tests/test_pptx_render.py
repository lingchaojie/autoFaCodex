from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from autofacodex.tools.pptx_render import render_pptx_pages, render_pptx_to_pdf


def test_render_pptx_to_pdf_uses_writable_profile_and_returns_pdf(tmp_path: Path):
    pptx = tmp_path / "candidate.v1.pptx"
    pptx.write_bytes(b"pptx")
    output_dir = tmp_path / "rendered-pdf"
    expected_pdf = output_dir / "candidate.v1.pdf"

    def fake_run(args, **kwargs):
        expected_pdf.parent.mkdir(parents=True, exist_ok=True)
        expected_pdf.write_bytes(b"%PDF-1.4")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="converted", stderr="")

    with patch("autofacodex.tools.pptx_render.subprocess.run", side_effect=fake_run) as run:
        result = render_pptx_to_pdf(pptx, output_dir, profile_root=tmp_path / "profiles")

    assert result == expected_pdf
    args = run.call_args.args[0]
    assert args[:3] == ["libreoffice", "--headless", "--convert-to"]
    assert any(str(arg).startswith("-env:UserInstallation=file://") for arg in args)
    assert run.call_args.kwargs["check"] is False
    assert run.call_args.kwargs["env"]["HOME"].startswith(str(tmp_path / "profiles"))


def test_render_pptx_to_pdf_reports_stdout_and_stderr_on_failure(tmp_path: Path):
    pptx = tmp_path / "candidate.v1.pptx"
    pptx.write_bytes(b"pptx")

    with patch(
        "autofacodex.tools.pptx_render.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["libreoffice"],
            returncode=7,
            stdout="stdout text",
            stderr="stderr text",
        ),
    ):
        with pytest.raises(RuntimeError, match="stdout text.*stderr text"):
            render_pptx_to_pdf(pptx, tmp_path / "rendered-pdf", profile_root=tmp_path / "profiles")


def test_render_pptx_pages_renders_pdf_pages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pptx = tmp_path / "candidate.v1.pptx"
    pptx.write_bytes(b"pptx")
    pdf = tmp_path / "candidate.v1.pdf"
    page = tmp_path / "page-001.png"

    monkeypatch.setattr("autofacodex.tools.pptx_render.render_pptx_to_pdf", lambda *_args, **_kwargs: pdf)
    monkeypatch.setattr("autofacodex.tools.pptx_render.render_pdf_pages", lambda *_args, **_kwargs: [page])

    result = render_pptx_pages(pptx, tmp_path / "ppt-render", profile_root=tmp_path / "profiles")

    assert result.output_pdf == pdf
    assert result.page_images == [page]
