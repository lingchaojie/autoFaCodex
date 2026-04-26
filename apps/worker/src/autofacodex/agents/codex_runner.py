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


def run_codex_agent(invocation: CodexInvocation, message: str, timeout_seconds: int = 900) -> subprocess.CompletedProcess[str]:
    validate_codex_auth(CodexAuthConfig(codex_home=invocation.codex_home, codex_bin=invocation.codex_bin))
    prompt = invocation.system_prompt.read_text(encoding="utf-8")
    full_message = f"{prompt}\n\nTask directory: {invocation.task_dir}\nSkill directory: {invocation.skill_dir}\n\n{message}"
    return subprocess.run(
        [invocation.codex_bin, "exec", "--dangerously-bypass-approvals-and-sandbox", full_message],
        cwd=invocation.task_dir,
        env={**os.environ, "CODEX_HOME": str(invocation.codex_home)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
