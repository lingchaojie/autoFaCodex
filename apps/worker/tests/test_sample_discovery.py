from pathlib import Path

import pytest

import autofacodex.evaluation.run_samples as samples


def _write_validator_report(task_dir: Path) -> None:
    reports = task_dir / "reports"
    reports.mkdir(parents=True)
    (reports / "validator.v1.json").write_text(
        f"""{{
          "task_id": "{task_dir.name}",
          "attempt": 1,
          "aggregate_status": "pass",
          "pages": [{{
            "page_number": 1,
            "status": "pass",
            "visual_score": 1.0,
            "editable_score": 1.0,
            "text_coverage_score": 1.0,
            "raster_fallback_ratio": 0.0,
            "issues": []
          }}]
        }}""",
        encoding="utf-8",
    )


def test_discover_pdfs_returns_sorted_pdfs_ignoring_office_temp_files(
    tmp_path: Path,
):
    samples_dir = tmp_path / "samples"
    samples_dir.mkdir()
    (samples_dir / "a.pdf").write_bytes(b"%PDF-1.4")
    (samples_dir / "~$b.pdf").write_bytes(b"%PDF-1.4")
    (samples_dir / "c.pptx").write_bytes(b"pptx")

    assert [path.name for path in samples.discover_pdfs(samples_dir)] == ["a.pdf"]


def test_run_samples_copies_inputs_to_task_dirs_and_runs_conversion(
    tmp_path: Path,
    monkeypatch,
):
    samples_dir = tmp_path / "samples"
    output_root = tmp_path / "evaluation"
    samples_dir.mkdir()
    (samples_dir / "b.pdf").write_bytes(b"pdf b")
    (samples_dir / "a.pdf").write_bytes(b"pdf a")

    calls: list[Path] = []

    def fake_run_pdf_to_ppt(task_dir: Path) -> None:
        calls.append(task_dir)
        _write_validator_report(task_dir)

    monkeypatch.setattr(samples, "run_pdf_to_ppt", fake_run_pdf_to_ppt)

    task_dirs = samples.run_samples(samples_dir, output_root)

    expected_task_dirs = [
        output_root / "sample-001-a",
        output_root / "sample-002-b",
    ]
    assert task_dirs == expected_task_dirs
    assert calls == expected_task_dirs
    assert (output_root / "sample-001-a" / "input.pdf").read_bytes() == b"pdf a"
    assert (output_root / "sample-002-b" / "input.pdf").read_bytes() == b"pdf b"


def test_run_samples_writes_aggregate_report(tmp_path: Path, monkeypatch):
    samples_dir = tmp_path / "samples"
    output_root = tmp_path / "evaluation"
    samples_dir.mkdir()
    (samples_dir / "a.pdf").write_bytes(b"pdf a")

    def fake_run_pdf_to_ppt(task_dir: Path) -> None:
        reports = task_dir / "reports"
        reports.mkdir(parents=True)
        (reports / "validator.v1.json").write_text(
            """{
              "task_id": "sample-001-a",
              "attempt": 1,
              "aggregate_status": "repair_needed",
              "pages": [{
                "page_number": 1,
                "status": "repair_needed",
                "visual_score": 0.75,
                "editable_score": 1.0,
                "text_coverage_score": 1.0,
                "raster_fallback_ratio": 0.0,
                "issues": [{"type": "visual_fidelity", "message": "low score", "suggested_action": "adjust layout"}]
              }]
            }""",
            encoding="utf-8",
        )

    monkeypatch.setattr(samples, "run_pdf_to_ppt", fake_run_pdf_to_ppt)

    samples.run_samples(samples_dir, output_root)

    summary = output_root / "evaluation-summary.json"
    assert summary.is_file()
    text = summary.read_text(encoding="utf-8")
    assert '"sample_count": 1' in text
    assert '"average_visual_score": 0.75' in text
    assert '"visual_fidelity": 1' in text


def test_run_samples_clears_stale_task_dir_and_wraps_conversion_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    samples_dir = tmp_path / "samples"
    output_root = tmp_path / "evaluation"
    samples_dir.mkdir()
    pdf_path = samples_dir / "a.pdf"
    pdf_path.write_bytes(b"fresh pdf")
    task_dir = output_root / "sample-001-a"
    stale_artifact = task_dir / "output" / "candidate.v1.pptx"
    stale_artifact.parent.mkdir(parents=True)
    stale_artifact.write_bytes(b"stale deck")
    original_error = RuntimeError("conversion failed")

    def fake_run_pdf_to_ppt(_task_dir: Path) -> None:
        raise original_error

    monkeypatch.setattr(samples, "run_pdf_to_ppt", fake_run_pdf_to_ppt)

    with pytest.raises(RuntimeError) as exc_info:
        samples.run_samples(samples_dir, output_root)

    assert not stale_artifact.exists()
    assert str(pdf_path) in str(exc_info.value)
    assert str(task_dir) in str(exc_info.value)
    assert exc_info.value.__cause__ is original_error
