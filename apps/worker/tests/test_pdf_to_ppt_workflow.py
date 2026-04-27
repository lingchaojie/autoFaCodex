import subprocess
from pathlib import Path

import fitz
import pytest
from pptx import Presentation
from reportlab.pdfgen import canvas

from autofacodex.config import WorkerConfig
from autofacodex.contracts import SlideModel, ValidatorReport
import autofacodex.workflows.pdf_to_ppt as workflow
from autofacodex.workflows.pdf_to_ppt import run_pdf_to_ppt


def make_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(400, 300))
    c.setFont("Helvetica", 24)
    c.drawString(72, 220, "Workflow Title 1")
    c.showPage()
    c.setFont("Helvetica", 24)
    c.drawString(72, 220, "Workflow Title 2")
    c.save()


def _write_validator_report(task_dir: Path, attempt: int, page_count: int) -> ValidatorReport:
    report = ValidatorReport(
        task_id=task_dir.name,
        attempt=attempt,
        aggregate_status="pass",
        pages=[
            {
                "page_number": page_number,
                "status": "pass",
                "visual_score": 1.0,
                "editable_score": 1.0,
                "text_coverage_score": 1.0,
                "raster_fallback_ratio": 0,
                "issues": [],
            }
            for page_number in range(1, page_count + 1)
        ],
    )
    (task_dir / "reports").mkdir(parents=True, exist_ok=True)
    (task_dir / "reports" / f"validator.v{attempt}.json").write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return report


def test_run_pdf_to_ppt_creates_candidate_report_and_slide_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    make_pdf(task_dir / "input.pdf")

    def fake_validate_candidate(received_task_dir: Path, attempt: int):
        assert received_task_dir == task_dir
        assert attempt == 1
        return _write_validator_report(received_task_dir, attempt, page_count=2)

    monkeypatch.setattr(
        workflow, "validate_candidate", fake_validate_candidate, raising=False
    )

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


def test_run_pdf_to_ppt_initial_uses_real_candidate_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    make_pdf(task_dir / "input.pdf")
    calls = []

    def fake_validate_candidate(received_task_dir: Path, attempt: int):
        calls.append((received_task_dir, attempt))
        report = ValidatorReport(
            task_id=received_task_dir.name,
            attempt=attempt,
            aggregate_status="repair_needed",
            pages=[
                {
                    "page_number": 1,
                    "status": "repair_needed",
                    "visual_score": 0.5,
                    "editable_score": 1.0,
                    "text_coverage_score": 1.0,
                    "raster_fallback_ratio": 0,
                    "issues": [],
                }
            ],
        )
        (received_task_dir / "reports").mkdir(parents=True, exist_ok=True)
        (received_task_dir / "reports" / "validator.v1.json").write_text(
            report.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return report

    monkeypatch.setattr(
        workflow, "validate_candidate", fake_validate_candidate, raising=False
    )

    run_pdf_to_ppt(task_dir)

    assert calls == [(task_dir, 1)]


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


def test_run_pdf_to_ppt_repair_invokes_runner_then_validator_and_logs_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    (task_dir / "task-manifest.json").write_text("{}", encoding="utf-8")
    (task_dir / "conversation").mkdir()
    (task_dir / "conversation" / "messages.jsonl").write_text(
        '{"role":"user","content":"Fix slide 2","createdAt":"2026-04-26T12:00:00.000Z"}\n',
        encoding="utf-8",
    )
    config = WorkerConfig(
        redis_url="redis://example",
        shared_tasks_dir=tmp_path,
        codex_home=tmp_path / "codex-home",
        codex_bin="codex-test",
    )
    calls = []
    results = [
        subprocess.CompletedProcess(
            args=["codex-test"], returncode=0, stdout="runner stdout", stderr="runner stderr"
        ),
        subprocess.CompletedProcess(
            args=["codex-test"],
            returncode=0,
            stdout="validator stdout",
            stderr="validator stderr",
        ),
    ]

    def fail_initial_extraction(*_args, **_kwargs):
        raise AssertionError("repair mode must not run deterministic initial extraction")

    def fake_run_codex_agent(invocation, message: str):
        calls.append((invocation, message))
        return results.pop(0)

    monkeypatch.setattr(workflow, "extract_pdf", fail_initial_extraction)
    monkeypatch.setattr(workflow, "load_config", lambda: config, raising=False)
    monkeypatch.setattr(workflow, "run_codex_agent", fake_run_codex_agent, raising=False)

    run_pdf_to_ppt(task_dir, mode="repair")

    assert [call[0].role for call in calls] == ["runner", "validator"]
    assert [call[0].task_dir for call in calls] == [task_dir, task_dir]
    assert calls[0][0].codex_home == config.codex_home
    assert calls[0][0].codex_bin == "codex-test"
    assert calls[0][0].system_prompt.as_posix().endswith(
        "agent_assets/runner/runner.system.md"
    )
    assert calls[0][0].skill_dir.as_posix().endswith("agent_assets/runner")
    assert calls[1][0].system_prompt.as_posix().endswith(
        "agent_assets/validator/validator.system.md"
    )
    assert calls[1][0].skill_dir.as_posix().endswith("agent_assets/validator")
    assert "task-manifest.json" in calls[0][1]
    assert "latest reports/validator.v*.json" in calls[0][1]
    assert "latest slides/slide-model.v*.json" in calls[0][1]
    assert "conversation/messages.jsonl" in calls[0][1]
    assert "produce a revised slide model" in calls[0][1]
    assert "validate every page after repair" in calls[1][1]
    assert "reports/validator.vN.json" in calls[1][1]
    assert (task_dir / "logs" / "runner-repair.log").read_text(encoding="utf-8") == (
        "returncode: 0\nstdout:\nrunner stdout\nstderr:\nrunner stderr\n"
    )
    assert (task_dir / "logs" / "validator-repair.log").read_text(encoding="utf-8") == (
        "returncode: 0\nstdout:\nvalidator stdout\nstderr:\nvalidator stderr\n"
    )


def test_run_pdf_to_ppt_repair_runner_failure_prevents_validator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    config = WorkerConfig(
        redis_url="redis://example",
        shared_tasks_dir=tmp_path,
        codex_home=tmp_path / "codex-home",
        codex_bin="codex-test",
    )
    calls = []

    def fake_run_codex_agent(invocation, message: str):
        calls.append((invocation, message))
        return subprocess.CompletedProcess(
            args=["codex-test"], returncode=7, stdout="runner stdout", stderr="runner failed"
        )

    monkeypatch.setattr(workflow, "load_config", lambda: config, raising=False)
    monkeypatch.setattr(workflow, "run_codex_agent", fake_run_codex_agent, raising=False)

    with pytest.raises(RuntimeError, match="Runner repair failed with return code 7"):
        run_pdf_to_ppt(task_dir, mode="repair")

    assert [call[0].role for call in calls] == ["runner"]
    assert (task_dir / "logs" / "runner-repair.log").read_text(encoding="utf-8") == (
        "returncode: 7\nstdout:\nrunner stdout\nstderr:\nrunner failed\n"
    )
    assert not (task_dir / "logs" / "validator-repair.log").exists()
