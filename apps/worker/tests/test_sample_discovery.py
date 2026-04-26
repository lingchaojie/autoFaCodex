from pathlib import Path

import pytest

import autofacodex.evaluation.run_samples as samples


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
