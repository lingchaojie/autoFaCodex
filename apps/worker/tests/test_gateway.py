import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from reportlab.pdfgen import canvas

from autofacodex.gateway import parse_job_payload, process_message, run_once, write_task_manifest


def make_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(400, 300))
    c.setFont("Helvetica", 24)
    c.drawString(72, 220, "Gateway Title")
    c.save()


def test_parse_job_payload():
    payload = json.dumps({"task_id": "task_1", "workflow_type": "pdf_to_ppt"})

    job = parse_job_payload(payload)

    assert job.task_id == "task_1"
    assert job.workflow_type == "pdf_to_ppt"


def test_parse_job_payload_rejects_extra_fields():
    payload = json.dumps({"task_id": "task_1", "workflow_type": "pdf_to_ppt", "extra": "field"})

    with pytest.raises(ValidationError):
        parse_job_payload(payload)


def test_parse_job_payload_rejects_unsupported_workflow_type():
    payload = json.dumps({"task_id": "task_1", "workflow_type": "other"})

    with pytest.raises(ValidationError):
        parse_job_payload(payload)


def test_parse_job_payload_rejects_empty_task_id():
    payload = json.dumps({"task_id": "", "workflow_type": "pdf_to_ppt"})

    with pytest.raises(ValidationError):
        parse_job_payload(payload)


def test_write_task_manifest(tmp_path: Path):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    (task_dir / "input.pdf").write_bytes(b"%PDF-1.4")

    manifest_path = write_task_manifest(task_dir, "task_1", 1, 3)

    assert manifest_path.name == "task-manifest.json"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["task_id"] == "task_1"


def test_run_once_writes_manifest_and_workflow_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    make_pdf(task_dir / "input.pdf")
    monkeypatch.setenv("SHARED_TASKS_DIR", str(tmp_path))

    run_once(json.dumps({"task_id": "task_1", "workflow_type": "pdf_to_ppt"}))

    assert (task_dir / "task-manifest.json").is_file()
    assert (task_dir / "logs" / "workflow.log").read_text(encoding="utf-8") == (
        "pdf_to_ppt workflow started\n"
    )
    assert (task_dir / "output" / "candidate.v1.pptx").is_file()
    assert (task_dir / "reports" / "validator.v1.json").is_file()


class FakeRedisClient:
    def __init__(self):
        self.acked: list[tuple[str, str, str]] = []

    def xack(self, stream: str, group: str, message_id: str) -> None:
        self.acked.append((stream, group, message_id))


def test_process_message_acks_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    make_pdf(task_dir / "input.pdf")
    monkeypatch.setenv("SHARED_TASKS_DIR", str(tmp_path))
    client = FakeRedisClient()

    process_message(
        client,
        "workflow_jobs",
        "worker",
        "message-1",
        {"payload": json.dumps({"task_id": "task_1", "workflow_type": "pdf_to_ppt"})},
    )

    assert client.acked == [("workflow_jobs", "worker", "message-1")]


def test_process_message_does_not_ack_failure(capsys: pytest.CaptureFixture[str]):
    client = FakeRedisClient()

    process_message(client, "workflow_jobs", "worker", "message-1", {"payload": "not json"})

    assert client.acked == []
    assert "Failed to process message message-1" in capsys.readouterr().err


def test_process_message_does_not_ack_invalid_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    (task_dir / "input.pdf").write_bytes(b"%PDF-1.4")
    monkeypatch.setenv("SHARED_TASKS_DIR", str(tmp_path))
    client = FakeRedisClient()

    process_message(
        client,
        "workflow_jobs",
        "worker",
        "message-1",
        {"payload": json.dumps({"task_id": "task_1", "workflow_type": "pdf_to_ppt"})},
    )

    assert client.acked == []
    assert "Failed to process message message-1" in capsys.readouterr().err
