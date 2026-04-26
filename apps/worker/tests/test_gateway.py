import json
from pathlib import Path

from autofacodex.gateway import parse_job_payload, write_task_manifest


def test_parse_job_payload():
    payload = json.dumps({"task_id": "task_1", "workflow_type": "pdf_to_ppt"})

    job = parse_job_payload(payload)

    assert job.task_id == "task_1"
    assert job.workflow_type == "pdf_to_ppt"


def test_write_task_manifest(tmp_path: Path):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    (task_dir / "input.pdf").write_bytes(b"%PDF-1.4")

    manifest_path = write_task_manifest(task_dir, "task_1", 1, 3)

    assert manifest_path.name == "task-manifest.json"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["task_id"] == "task_1"
