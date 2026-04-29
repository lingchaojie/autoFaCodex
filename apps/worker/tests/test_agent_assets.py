from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from autofacodex.agents.codex_runner import CodexInvocation, run_codex_agent


def test_runner_prompt_forbids_full_page_screenshot():
    text = Path("agent_assets/runner/runner.system.md").read_text(encoding="utf-8")
    assert "full-page screenshot" in text
    assert "Validator report" in text
    assert "source of truth" in text
    assert "structured repair report" in text
    assert "Do not invent missing artifacts" in text


def test_validator_prompt_requires_every_page():
    text = Path("agent_assets/validator/validator.system.md").read_text(encoding="utf-8")
    assert "every page" in text
    assert "editable" in text
    assert "strict valid JSON" in text
    assert "aggregate status" in text
    assert "evidence paths" in text


def test_runner_prompt_requires_evidence_based_slide_model_repair():
    text = Path("agent_assets/runner/runner.system.md").read_text(encoding="utf-8")
    assert "reports/validator.vN.json" in text
    assert "slides/slide-model.vN.json" in text
    assert "runner-repair.vN.json" in text
    assert "Do not validate your own output" in text
    assert "bounded raster fallback" in text
    assert "use deterministic project tools for slide-model repair and PPTX generation" in text
    assert (
        "must not run rendering, diffing, scoring, or inspection to make "
        "pass/fail validation decisions"
    ) in text


def test_runner_prompt_requires_generic_background_foreground_reconstruction():
    text = Path("agent_assets/runner/runner.system.md").read_text(encoding="utf-8")
    skill = Path("agent_assets/runner/SKILL.md").read_text(encoding="utf-8")
    combined = f"{text}\n{skill}"

    assert "Do not hard-code sample-specific layouts" in combined
    assert "PDF background" in combined
    assert "role" in combined
    assert "background" in combined
    assert "foreground" in combined
    assert "table" in combined
    assert "path" in combined
    assert "semantic_table" in combined
    assert "guarded semantic table repair tool" in combined


def test_runner_prompt_requires_noop_artifacts_when_repair_is_uncertain():
    text = Path("agent_assets/runner/runner.system.md").read_text(encoding="utf-8")
    skill = Path("agent_assets/runner/SKILL.md").read_text(encoding="utf-8")
    combined = f"{text}\n{skill}"

    assert "no-op repair" in combined
    assert "copy the latest slide model" in combined
    assert "still generate the required target PPTX" in combined


def test_validator_prompt_allows_declared_pdf_backgrounds_only():
    text = Path("agent_assets/validator/validator.system.md").read_text(encoding="utf-8")
    skill = Path("agent_assets/validator/SKILL.md").read_text(encoding="utf-8")
    combined = f"{text}\n{skill}"

    assert "PDF background" in combined
    assert "foreground" in combined
    assert "not fail a slide only because it contains a declared PDF background" in combined
    assert "reject full-page screenshots" in combined


def test_validator_prompt_requires_real_evidence_paths():
    text = Path("agent_assets/validator/validator.system.md").read_text(encoding="utf-8")
    assert "PDF render" in text
    assert "PPTX render" in text
    assert "visual diff" in text
    assert "text coverage" in text
    assert "full-page picture" in text
    assert "evidence_paths" in text


def test_pdf_to_ppt_agents_require_region_hints_and_constrained_repair_actions():
    runner = Path("agent_assets/runner/runner.system.md").read_text(encoding="utf-8")
    runner_skill = Path("agent_assets/runner/SKILL.md").read_text(encoding="utf-8")
    validator = Path("agent_assets/validator/validator.system.md").read_text(encoding="utf-8")
    validator_skill = Path("agent_assets/validator/SKILL.md").read_text(encoding="utf-8")
    combined_runner = runner + "\n" + runner_skill
    combined_validator = validator + "\n" + validator_skill

    assert "constrained repair action" in combined_runner
    assert "repair_hints" in combined_runner
    assert "region evidence" in combined_validator
    assert "repair_hints" in combined_validator


def test_run_codex_agent_validates_auth_and_runs_with_stdin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    system_prompt = tmp_path / "runner.system.md"
    system_prompt.write_text("System prompt", encoding="utf-8")
    skill_dir = tmp_path / "runner"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Skill", encoding="utf-8")
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    monkeypatch.setenv("AUTOFACODEX_TEST_ENV", "preserved")

    invocation = CodexInvocation(
        role="runner",
        task_dir=task_dir,
        system_prompt=system_prompt,
        skill_dir=skill_dir,
        codex_home=codex_home,
        codex_bin="codex",
    )
    completed = subprocess.CompletedProcess(args=["codex"], returncode=0, stdout="ok", stderr="")

    with (
        patch("autofacodex.agents.codex_runner.validate_codex_auth") as validate_auth,
        patch("autofacodex.agents.codex_runner.subprocess.run", return_value=completed) as run,
    ):
        result = run_codex_agent(invocation, "Repair page 2", timeout_seconds=123)

    assert result is completed
    validate_auth.assert_called_once()
    auth_config = validate_auth.call_args.args[0]
    assert auth_config.codex_home == codex_home
    assert auth_config.codex_bin == "codex"
    run.assert_called_once()
    assert run.call_args.args[0] == [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        "-",
    ]
    kwargs = run.call_args.kwargs
    assert kwargs["cwd"] == task_dir
    assert kwargs["env"]["AUTOFACODEX_TEST_ENV"] == "preserved"
    assert kwargs["env"]["CODEX_HOME"] == str(codex_home)
    assert kwargs["stdout"] == subprocess.PIPE
    assert kwargs["stderr"] == subprocess.PIPE
    assert kwargs["text"] is True
    assert kwargs["timeout"] == 123
    assert kwargs["check"] is False
    assert kwargs["input"] == (
        "You were dispatched as a subprocess agent for this one task. "
        "Use only the role instructions and the listed task skill directory; "
        "do not load global conversation skills.\n\n"
        "System prompt\n\n"
        f"Role: runner\nTask directory: {task_dir}\nSkill directory: {skill_dir}\n\n"
        "Repair page 2"
    )


def test_run_codex_agent_uses_timeout_from_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    system_prompt = tmp_path / "runner.system.md"
    system_prompt.write_text("System prompt", encoding="utf-8")
    skill_dir = tmp_path / "runner"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Skill", encoding="utf-8")
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    monkeypatch.setenv("CODEX_AGENT_TIMEOUT_SECONDS", "45")
    invocation = CodexInvocation(
        role="runner",
        task_dir=task_dir,
        system_prompt=system_prompt,
        skill_dir=skill_dir,
        codex_home=codex_home,
        codex_bin="codex",
    )
    completed = subprocess.CompletedProcess(args=["codex"], returncode=0, stdout="ok", stderr="")

    with (
        patch("autofacodex.agents.codex_runner.validate_codex_auth"),
        patch("autofacodex.agents.codex_runner.subprocess.run", return_value=completed) as run,
    ):
        run_codex_agent(invocation, "Repair page 2")

    assert run.call_args.kwargs["timeout"] == 45


@pytest.mark.parametrize(
    ("missing_path", "match"),
    [
        ("task_dir", "runner.*task_dir"),
        ("system_prompt", "runner.*system_prompt"),
        ("skill_dir", "runner.*skill_dir"),
        ("skill_file", "runner.*SKILL.md"),
    ],
)
def test_run_codex_agent_rejects_missing_paths(tmp_path: Path, missing_path: str, match: str):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    system_prompt = tmp_path / "runner.system.md"
    system_prompt.write_text("System prompt", encoding="utf-8")
    skill_dir = tmp_path / "runner"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("# Skill", encoding="utf-8")
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()

    if missing_path == "task_dir":
        task_dir.rmdir()
    elif missing_path == "system_prompt":
        system_prompt.unlink()
    elif missing_path == "skill_dir":
        skill_file.unlink()
        skill_dir.rmdir()
    elif missing_path == "skill_file":
        skill_file.unlink()

    invocation = CodexInvocation(
        role="runner",
        task_dir=task_dir,
        system_prompt=system_prompt,
        skill_dir=skill_dir,
        codex_home=codex_home,
        codex_bin="codex",
    )

    with (
        patch("autofacodex.agents.codex_runner.validate_codex_auth"),
        patch("autofacodex.agents.codex_runner.subprocess.run") as run,
        pytest.raises(FileNotFoundError, match=match),
    ):
        run_codex_agent(invocation, "Repair page 2")

    run.assert_not_called()
