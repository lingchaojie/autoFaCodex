from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from autofacodex.tools.pptx_render import render_pptx_pages, render_pptx_to_pdf


def _user_installation_arg(args: list[str]) -> str:
    return next(arg for arg in args if arg.startswith("-env:UserInstallation="))


def _assert_preserves_runtime_env_with_fontconfig(kwargs: dict) -> None:
    env = kwargs["env"]
    assert env["FONTCONFIG_FILE"].endswith("fontconfig-windows-fonts.conf")
    assert "HOME" in env


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
    _assert_preserves_runtime_env_with_fontconfig(run.call_args.kwargs)


def test_render_pptx_to_pdf_uses_configured_fontconfig_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    pptx = tmp_path / "candidate.pptx"
    pptx.write_bytes(b"pptx")
    output_dir = tmp_path / "rendered-pdf"
    expected_pdf = output_dir / "candidate.pdf"
    fontconfig_file = tmp_path / "fontconfig.conf"
    fontconfig_file.write_text("<fontconfig/>", encoding="utf-8")

    def fake_run(args, **kwargs):
        expected_pdf.write_bytes(b"%PDF-1.4")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "autofacodex.tools.pptx_render.WINDOWS_FONTCONFIG_FILE",
        fontconfig_file,
        raising=False,
    )

    with patch("autofacodex.tools.pptx_render.subprocess.run", side_effect=fake_run) as run:
        render_pptx_to_pdf(pptx, output_dir, profile_root=tmp_path / "profiles")

    assert run.call_args.kwargs["env"]["FONTCONFIG_FILE"] == str(fontconfig_file)


def test_render_pptx_to_pdf_defaults_profile_under_output_dir(tmp_path: Path):
    pptx = tmp_path / "readonly-input" / "candidate.pptx"
    pptx.parent.mkdir()
    pptx.write_bytes(b"pptx")
    output_dir = tmp_path / "rendered-pdf"
    expected_pdf = output_dir / "candidate.pdf"

    def fake_run(args, **kwargs):
        expected_pdf.write_bytes(b"%PDF-1.4")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with patch("autofacodex.tools.pptx_render.subprocess.run", side_effect=fake_run) as run:
        render_pptx_to_pdf(pptx, output_dir)

    _assert_preserves_runtime_env_with_fontconfig(run.call_args.kwargs)
    assert _user_installation_arg(run.call_args.args[0]).startswith(
        f"-env:UserInstallation={(output_dir / '.libreoffice').resolve().as_uri()}"
    )


def test_render_pptx_to_pdf_uses_unique_profile_per_call(tmp_path: Path):
    pptx = tmp_path / "candidate.pptx"
    pptx.write_bytes(b"pptx")
    output_dir = tmp_path / "rendered-pdf"
    expected_pdf = output_dir / "candidate.pdf"

    def fake_run(args, **kwargs):
        expected_pdf.write_bytes(b"%PDF-1.4")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with patch("autofacodex.tools.pptx_render.subprocess.run", side_effect=fake_run) as run:
        render_pptx_to_pdf(pptx, output_dir, profile_root=tmp_path / "profiles")
        render_pptx_to_pdf(pptx, output_dir, profile_root=tmp_path / "profiles")

    first_args = run.call_args_list[0].args[0]
    second_args = run.call_args_list[1].args[0]
    assert _user_installation_arg(first_args) != _user_installation_arg(second_args)


def test_render_pptx_to_pdf_does_not_override_home_or_runtime_env(tmp_path: Path):
    pptx = tmp_path / "candidate.pptx"
    pptx.write_bytes(b"pptx")
    output_dir = tmp_path / "rendered-pdf"
    expected_pdf = output_dir / "candidate.pdf"

    def fake_run(args, **kwargs):
        expected_pdf.write_bytes(b"%PDF-1.4")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with patch("autofacodex.tools.pptx_render.subprocess.run", side_effect=fake_run) as run:
        render_pptx_to_pdf(pptx, output_dir, profile_root=tmp_path / "profiles")

    _assert_preserves_runtime_env_with_fontconfig(run.call_args.kwargs)


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
        with pytest.raises(RuntimeError, match="stdout text.*stderr text") as exc_info:
            render_pptx_to_pdf(pptx, tmp_path / "rendered-pdf", profile_root=tmp_path / "profiles")
    assert not isinstance(exc_info.value, FileNotFoundError)


def test_render_pptx_to_pdf_missing_output_with_success_raises_file_not_found(tmp_path: Path):
    pptx = tmp_path / "candidate.pptx"
    pptx.write_bytes(b"pptx")

    with patch(
        "autofacodex.tools.pptx_render.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["libreoffice"],
            returncode=0,
            stdout="stdout text",
            stderr="stderr text",
        ),
    ):
        with pytest.raises(FileNotFoundError, match="stdout text.*stderr text"):
            render_pptx_to_pdf(pptx, tmp_path / "rendered-pdf", profile_root=tmp_path / "profiles")


def test_render_pptx_pages_renders_pdf_pages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pptx = tmp_path / "candidate.v1.pptx"
    pptx.write_bytes(b"pptx")
    pdf = tmp_path / "candidate.v1.pdf"
    page = tmp_path / "page-001.png"
    output_dir = tmp_path / "ppt-render"
    profile_root = tmp_path / "profiles"
    calls = {}

    def fake_render_pptx_to_pdf(*args, **kwargs):
        calls["pptx_to_pdf"] = (args, kwargs)
        return pdf

    def fake_render_pdf_pages(*args, **kwargs):
        calls["pdf_pages"] = (args, kwargs)
        return [page]

    monkeypatch.setattr("autofacodex.tools.pptx_render.render_pptx_to_pdf", fake_render_pptx_to_pdf)
    monkeypatch.setattr("autofacodex.tools.pptx_render.render_pdf_pages", fake_render_pdf_pages)

    result = render_pptx_pages(
        pptx,
        output_dir,
        zoom=3.0,
        profile_root=profile_root,
        libreoffice_bin="soffice",
    )

    assert result.output_pdf == pdf
    assert result.page_images == [page]
    assert calls["pptx_to_pdf"] == (
        (pptx, output_dir / "rendered-pdf"),
        {"profile_root": profile_root, "libreoffice_bin": "soffice"},
    )
    assert calls["pdf_pages"] == ((pdf, output_dir / "rendered-pages"), {"zoom": 3.0})
