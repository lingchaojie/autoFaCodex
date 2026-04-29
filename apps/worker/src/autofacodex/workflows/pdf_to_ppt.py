from pathlib import Path
import subprocess
from typing import Literal

from autofacodex.agents.codex_runner import CodexInvocation, run_codex_agent
from autofacodex.config import load_config
from autofacodex.tools.pdf_extract import extract_pdf
from autofacodex.tools.pdf_render import render_pdf_pages
from autofacodex.tools.pptx_generate import generate_pptx
from autofacodex.tools.slide_model_builder import build_initial_slide_model
from autofacodex.tools.validate_candidate import validate_candidate


WORKFLOW_DIRS = [
    "extracted",
    "renders/pdf",
    "renders/ppt",
    "renders/diff",
    "slides",
    "output",
    "reports",
    "logs",
]

WORKER_ROOT = Path(__file__).resolve().parents[3]
AGENT_ASSETS_DIR = WORKER_ROOT / "agent_assets"


def _python_executable() -> str:
    venv_python = WORKER_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return "python"


def _agent_tool_context() -> str:
    python = _python_executable()
    source_dir = WORKER_ROOT / "src"
    return (
        "Deterministic tool context:\n"
        f"- Worker source directory: {source_dir}\n"
        f"- Python executable: {python}\n"
        "- Run commands from the task directory and write outputs only inside that task directory.\n"
        "- Regenerate a PPTX from a revised slide model with:\n"
        f"  PYTHONPATH={source_dir} {python} -m autofacodex.tools.generate_pptx_from_model "
        "slides/slide-model.vN.json output/candidate.vN.pptx --asset-root .\n"
        "- Inspect PPTX editability from Python with "
        "`from autofacodex.tools.pptx_inspect import inspect_pptx_editability`.\n"
        "- Compare rendered images from Python with "
        "`from autofacodex.tools.visual_diff import compare_images`.\n"
    )


def _validate_pdf_renders(render_paths: list[Path], expected_count: int) -> None:
    if len(render_paths) != expected_count:
        raise RuntimeError(f"Expected {expected_count} PDF renders, got {len(render_paths)}")

    missing_paths = [path for path in render_paths if not path.exists()]
    if missing_paths:
        missing = ", ".join(str(path) for path in missing_paths)
        raise RuntimeError(f"PDF render does not exist: {missing}")


def _write_agent_log(path: Path, result: subprocess.CompletedProcess[str]) -> None:
    path.write_text(
        f"returncode: {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}\n",
        encoding="utf-8",
    )


def _codex_invocation(role: Literal["runner", "validator"], task_dir: Path) -> CodexInvocation:
    config = load_config()
    skill_dir = AGENT_ASSETS_DIR / role
    return CodexInvocation(
        role=role,
        task_dir=task_dir,
        system_prompt=skill_dir / f"{role}.system.md",
        skill_dir=skill_dir,
        codex_home=config.codex_home,
        codex_bin=config.codex_bin,
    )


def _run_repair(task_dir: Path) -> None:
    logs_dir = task_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    runner_message = (
        "Repair this existing pdf_to_ppt task. Read task-manifest.json, "
        "latest reports/validator.v*.json, latest slides/slide-model.v*.json, "
        "and conversation/messages.jsonl if present. Do not rerun deterministic "
        "initial PDF extraction. Do exactly one single bounded repair pass: focus "
        "on the first one or two failed pages unless the user named specific pages, "
        "avoid full-deck visual exploration, and exit after writing artifacts. Do "
        "not render, diff, or visually validate the PPTX; that is the Validator's "
        "responsibility. Then "
        "produce a revised slide model, PPTX candidate, and repair report/event in "
        "the task directory. If no confident repair is possible in this bounded "
        "pass, write the repair report/event with the reason and exit without "
        "looping.\n\n"
        f"{_agent_tool_context()}"
    )
    runner_result = run_codex_agent(_codex_invocation("runner", task_dir), runner_message)
    _write_agent_log(logs_dir / "runner-repair.log", runner_result)
    if runner_result.returncode != 0:
        raise RuntimeError(
            f"Runner repair failed with return code {runner_result.returncode}"
        )

    validator_message = (
        "Please validate every page after repair. Read task-manifest.json, the "
        "latest slides/slide-model.v*.json, the latest PPTX candidate, renders, "
        "and repair evidence, then write reports/validator.vN.json as strict "
        "valid JSON.\n\n"
        f"{_agent_tool_context()}"
    )
    validator_result = run_codex_agent(
        _codex_invocation("validator", task_dir), validator_message
    )
    _write_agent_log(logs_dir / "validator-repair.log", validator_result)
    if validator_result.returncode != 0:
        raise RuntimeError(
            f"Validator repair failed with return code {validator_result.returncode}"
        )


def _run_initial(task_dir: Path) -> None:
    for directory in WORKFLOW_DIRS:
        (task_dir / directory).mkdir(parents=True, exist_ok=True)

    (task_dir / "logs" / "workflow.log").write_text(
        "pdf_to_ppt workflow started\n", encoding="utf-8"
    )

    pdf_path = task_dir / "input.pdf"
    extracted = extract_pdf(pdf_path, task_dir / "extracted")
    page_count = len(extracted["pages"])
    pdf_renders = render_pdf_pages(pdf_path, task_dir / "renders" / "pdf")
    _validate_pdf_renders(pdf_renders, page_count)

    slide_model = build_initial_slide_model(extracted)
    (task_dir / "slides" / "slide-model.v1.json").write_text(
        slide_model.model_dump_json(indent=2), encoding="utf-8"
    )

    generate_pptx(slide_model, task_dir / "output" / "candidate.v1.pptx")
    validate_candidate(task_dir, attempt=1)


def run_pdf_to_ppt(
    task_dir: Path, mode: Literal["initial", "repair"] = "initial"
) -> None:
    if mode == "initial":
        _run_initial(task_dir)
        return
    if mode == "repair":
        _run_repair(task_dir)
        return
    raise ValueError(f"Unsupported pdf_to_ppt mode: {mode}")
