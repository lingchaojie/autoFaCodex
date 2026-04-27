import sys
import time
from pathlib import Path
from typing import Literal

from pydantic import Field

from autofacodex.config import load_config
from autofacodex.contracts import ContractModel, TaskManifest
from autofacodex.workflows.pdf_to_ppt import run_pdf_to_ppt


class WorkflowJob(ContractModel):
    task_id: str = Field(min_length=1)
    workflow_type: Literal["pdf_to_ppt"]
    mode: Literal["initial", "repair"] = "initial"


def parse_job_payload(payload: str) -> WorkflowJob:
    return WorkflowJob.model_validate_json(payload)


def write_task_manifest(task_dir: Path, task_id: str, attempt: int, max_attempts: int) -> Path:
    manifest = TaskManifest(
        task_id=task_id,
        workflow_type="pdf_to_ppt",
        input_pdf="input.pdf",
        attempt=attempt,
        max_attempts=max_attempts,
    )
    path = task_dir / "task-manifest.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path


def run_once(payload: str) -> None:
    config = load_config()
    job = parse_job_payload(payload)
    task_dir = config.shared_tasks_dir / job.task_id
    write_task_manifest(task_dir, job.task_id, attempt=1, max_attempts=3)
    run_pdf_to_ppt(task_dir, mode=job.mode)


def process_message(client, stream: str, group: str, message_id: str, fields: dict[str, str]) -> None:
    try:
        run_once(fields["payload"])
    except Exception as exc:
        print(f"Failed to process message {message_id}: {exc}", file=sys.stderr)
        return
    client.xack(stream, group, message_id)


def main() -> None:
    import redis

    config = load_config()
    client = redis.Redis.from_url(config.redis_url, decode_responses=True)
    stream = "workflow_jobs"
    group = "worker"
    consumer = "worker-1"
    try:
        client.xgroup_create(stream, group, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise
    while True:
        messages = client.xreadgroup(group, consumer, {stream: ">"}, count=1, block=5000)
        if not messages:
            time.sleep(1)
            continue
        for _, entries in messages:
            for message_id, fields in entries:
                process_message(client, stream, group, message_id, fields)


if __name__ == "__main__":
    main()
