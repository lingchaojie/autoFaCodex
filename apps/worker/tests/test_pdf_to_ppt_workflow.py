from pathlib import Path

import fitz
import pytest
from pptx import Presentation
from reportlab.pdfgen import canvas

from autofacodex.contracts import SlideModel, ValidatorReport
from autofacodex.workflows.pdf_to_ppt import run_pdf_to_ppt


def make_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(400, 300))
    c.setFont("Helvetica", 24)
    c.drawString(72, 220, "Workflow Title 1")
    c.showPage()
    c.setFont("Helvetica", 24)
    c.drawString(72, 220, "Workflow Title 2")
    c.save()


def test_run_pdf_to_ppt_creates_candidate_report_and_slide_model(tmp_path: Path):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    make_pdf(task_dir / "input.pdf")

    run_pdf_to_ppt(task_dir)

    assert (task_dir / "output" / "candidate.v1.pptx").is_file()
    assert (task_dir / "reports" / "validator.v1.json").is_file()
    assert (task_dir / "slides" / "slide-model.v1.json").is_file()

    model = SlideModel.model_validate_json(
        (task_dir / "slides" / "slide-model.v1.json").read_text(encoding="utf-8")
    )
    report = ValidatorReport.model_validate_json(
        (task_dir / "reports" / "validator.v1.json").read_text(encoding="utf-8")
    )
    presentation = Presentation(task_dir / "output" / "candidate.v1.pptx")

    assert [slide.page_number for slide in model.slides] == [1, 2]
    assert [page.page_number for page in report.pages] == [1, 2]
    assert len(presentation.slides) == len(model.slides) == len(report.pages)


def test_run_pdf_to_ppt_rejects_invalid_pdf(tmp_path: Path):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    (task_dir / "input.pdf").write_bytes(b"%PDF-1.4")

    with pytest.raises(fitz.FileDataError):
        run_pdf_to_ppt(task_dir)

    assert not (task_dir / "output" / "candidate.v1.pptx").exists()


def test_run_pdf_to_ppt_rejects_missing_pdf_renders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    make_pdf(task_dir / "input.pdf")

    monkeypatch.setattr("autofacodex.workflows.pdf_to_ppt.render_pdf_pages", lambda *_: [])

    with pytest.raises(RuntimeError, match="Expected 2 PDF renders"):
        run_pdf_to_ppt(task_dir)

    assert not (task_dir / "output" / "candidate.v1.pptx").exists()
    assert not (task_dir / "reports" / "validator.v1.json").exists()


def test_run_pdf_to_ppt_rejects_nonexistent_pdf_render_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    make_pdf(task_dir / "input.pdf")

    monkeypatch.setattr(
        "autofacodex.workflows.pdf_to_ppt.render_pdf_pages",
        lambda *_: [task_dir / "missing-1.png", task_dir / "missing-2.png"],
    )

    with pytest.raises(RuntimeError, match="PDF render does not exist"):
        run_pdf_to_ppt(task_dir)

    assert not (task_dir / "output" / "candidate.v1.pptx").exists()
    assert not (task_dir / "reports" / "validator.v1.json").exists()
