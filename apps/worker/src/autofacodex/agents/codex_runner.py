import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from autofacodex.agents.codex_auth import CodexAuthConfig, validate_codex_auth


@dataclass(frozen=True)
class CodexInvocation:
    role: str
    task_dir: Path
    system_prompt: Path
    skill_dir: Path
    codex_home: Path
    codex_bin: str


def _default_timeout_seconds() -> int:
    raw_value = os.environ.get("CODEX_AGENT_TIMEOUT_SECONDS")
    if raw_value is None:
        return 900
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError("CODEX_AGENT_TIMEOUT_SECONDS must be a positive integer") from exc
    if value <= 0:
        raise ValueError("CODEX_AGENT_TIMEOUT_SECONDS must be a positive integer")
    return value


def _require_path(condition: bool, role: str, label: str, path: Path) -> None:
    if not condition:
        raise FileNotFoundError(f"{role} {label} not found: {path}")


def run_codex_agent(
    invocation: CodexInvocation, message: str, timeout_seconds: int | None = None
) -> subprocess.CompletedProcess[str]:
    _require_path(invocation.task_dir.is_dir(), invocation.role, "task_dir", invocation.task_dir)
    _require_path(invocation.system_prompt.is_file(), invocation.role, "system_prompt", invocation.system_prompt)
    _require_path(invocation.skill_dir.is_dir(), invocation.role, "skill_dir", invocation.skill_dir)
    _require_path((invocation.skill_dir / "SKILL.md").is_file(), invocation.role, "SKILL.md", invocation.skill_dir / "SKILL.md")
    validate_codex_auth(CodexAuthConfig(codex_home=invocation.codex_home, codex_bin=invocation.codex_bin))
    prompt = invocation.system_prompt.read_text(encoding="utf-8")
    full_message = (
        "You were dispatched as a subprocess agent for this one task. "
        "Use only the role instructions and the listed task skill directory; "
        "do not load global conversation skills.\n\n"
        f"{prompt}\n\n"
        f"Role: {invocation.role}\nTask directory: {invocation.task_dir}\nSkill directory: {invocation.skill_dir}\n\n"
        f"{message}"
    )
    return subprocess.run(
        [
            invocation.codex_bin,
            "exec",
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            "-",
        ],
        cwd=invocation.task_dir,
        env={**os.environ, "CODEX_HOME": str(invocation.codex_home)},
        input=full_message,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_seconds if timeout_seconds is not None else _default_timeout_seconds(),
        check=False,
    )
