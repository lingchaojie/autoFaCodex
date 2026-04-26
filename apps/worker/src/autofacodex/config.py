import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkerConfig:
    redis_url: str
    shared_tasks_dir: Path
    codex_home: Path
    codex_bin: str


def load_config() -> WorkerConfig:
    return WorkerConfig(
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        shared_tasks_dir=Path(os.environ.get("SHARED_TASKS_DIR", "shared-tasks")),
        codex_home=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))),
        codex_bin=os.environ.get("CODEX_BIN", "codex"),
    )
