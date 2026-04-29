import subprocess
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image

from autofacodex.agents.validator_runtime import build_validator_report
from autofacodex.tools.pptx_inspect import inspect_pptx_editability
from autofacodex.tools.pptx_render import render_pptx_to_pdf
from autofacodex.tools.visual_diff import compare_images


def test_build_validator_report_fails_full_page_raster(tmp_path: Path):
    report = build_validator_report(
        task_id="task_1",
        attempt=1,
        page_count=1,
        visual_scores={1: 0.98},
        editable_scores={1: 0.1},
        text_scores={1: 0.0},
        raster_ratios={1: 0.95},
    )

    page = report.pages[0]
    assert page.status == "repair_needed"
    assert page.issues[0].type == "editability"


def test_build_validator_report_rejects_invalid_page_count():
    with pytest.raises(ValueError, match="page_count"):
        build_validator_report(
            task_id="task_1",
            attempt=1,
            page_count=0,
            visual_scores={},
            editable_scores={},
            text_scores={},
            raster_ratios={},
        )


def _write_image(path: Path, color: int, size: tuple[int, int] = (8, 8)) -> None:
    Image.new("L", size, color=color).save(path)


def test_compare_images_returns_one_for_identical_images(tmp_path: Path):
    reference = tmp_path / "reference.png"
    candidate = tmp_path / "candidate.png"
    _write_image(reference, color=128)
    _write_image(candidate, color=128)

    assert compare_images(reference, candidate) == pytest.approx(1.0)


def test_compare_images_returns_low_score_for_different_images(tmp_path: Path):
    reference = tmp_path / "reference.png"
    candidate = tmp_path / "candidate.png"
    _write_image(reference, color=0)
    _write_image(candidate, color=255)

    assert compare_images(reference, candidate) < 0.1


def test_compare_images_handles_tiny_identical_images(tmp_path: Path):
    reference = tmp_path / "reference.png"
    candidate = tmp_path / "candidate.png"
    _write_image(reference, color=64, size=(4, 4))
    _write_image(candidate, color=64, size=(4, 4))

    assert compare_images(reference, candidate) == pytest.approx(1.0)


def test_render_pptx_to_pdf_raises_when_libreoffice_does_not_write_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="converted", stderr="warning"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(FileNotFoundError, match="deck.pdf.*converted.*warning"):
        render_pptx_to_pdf(pptx, tmp_path / "renders")


def test_inspect_pptx_editability_counts_slide_xml_nodes_and_ignores_non_slides(
    tmp_path: Path,
):
    pptx = tmp_path / "deck.pptx"
    slide_xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:sp><p:txBody><a:p><a:r><a:t xml:space="preserve"> Title </a:t></a:r></a:p></p:txBody></p:sp>
      <p:pic />
    </p:spTree>
  </p:cSld>
</p:sld>
"""
    non_slide_xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld><p:spTree><p:sp><a:t>Ignored</a:t></p:sp></p:spTree></p:cSld>
</p:sld>
"""
    with ZipFile(pptx, "w") as archive:
        archive.writestr("ppt/slides/slide1.xml", slide_xml)
        archive.writestr("ppt/slides/slide1-not-a-slide.xml", non_slide_xml)

    report = inspect_pptx_editability(pptx)

    assert len(report["pages"]) == 1
    page = report["pages"][0]
    assert page["slide"] == "ppt/slides/slide1.xml"
    assert page["text_runs"] == 1
    assert page["pictures"] == 1
    assert page["shapes"] == 1
    assert page["text"] == " Title "
    assert page["largest_picture_area_ratio"] == 0.0
    assert page["has_full_page_picture"] is False


def test_inspect_pptx_editability_sorts_slides_numerically(tmp_path: Path):
    pptx = tmp_path / "deck.pptx"
    slide_xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" />
"""
    with ZipFile(pptx, "w") as archive:
        archive.writestr("ppt/slides/slide1.xml", slide_xml)
        archive.writestr("ppt/slides/slide10.xml", slide_xml)
        archive.writestr("ppt/slides/slide2.xml", slide_xml)

    report = inspect_pptx_editability(pptx)

    assert [page["slide"] for page in report["pages"]] == [
        "ppt/slides/slide1.xml",
        "ppt/slides/slide2.xml",
        "ppt/slides/slide10.xml",
    ]
