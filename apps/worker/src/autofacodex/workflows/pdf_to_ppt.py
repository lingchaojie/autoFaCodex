from pathlib import Path
import re
import subprocess
from typing import Literal

from autofacodex.agents.codex_runner import CodexInvocation, run_codex_agent
from autofacodex.config import load_config
from autofacodex.contracts import SlideModel, TaskManifest, ValidatorReport
from autofacodex.tools.pdf_extract import extract_pdf
from autofacodex.tools.pdf_render import render_pdf_pages
from autofacodex.tools.pptx_generate import generate_pptx
from autofacodex.tools.runner_repair import run_deterministic_runner_repair
from autofacodex.tools.semantic_table_repair import upgrade_semantic_tables_with_guard
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
_VALIDATOR_REPORT_PATTERN = re.compile(r"^validator\.v(\d+)\.json$")
_SLIDE_MODEL_PATTERN = re.compile(r"^slide-model\.v(\d+)\.json$")
_STATUS_PRIORITY = ("failed", "repair_needed", "manual_review", "pass")


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
        "- Try guarded promotion of `semantic_table` overlays to visible editable PPT tables with:\n"
        f"  PYTHONPATH={source_dir} {python} -m autofacodex.tools.semantic_table_repair "
        ". --source-attempt N\n"
        "- If you cannot complete a confident repair quickly, create the required bounded fallback "
        "repair artifacts with:\n"
        f"  PYTHONPATH={source_dir} {python} -m autofacodex.tools.runner_repair "
        ". --source-attempt N --target-attempt M --reason bounded_noop\n"
        "- Run deterministic validation for an attempt with:\n"
        f"  PYTHONPATH={source_dir} {python} -c "
        "\"from pathlib import Path; from autofacodex.tools.validate_candidate import validate_candidate; "
        "validate_candidate(Path('.'), attempt=N)\"\n"
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


def _load_task_manifest(task_dir: Path) -> TaskManifest | None:
    manifest_path = task_dir / "task-manifest.json"
    if not manifest_path.exists():
        return None
    return TaskManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))


def _repair_attempt_limit(task_dir: Path) -> int:
    manifest = _load_task_manifest(task_dir)
    if manifest is None:
        return 1
    return manifest.max_attempts


def _resolved_aggregate_status(report: ValidatorReport) -> str:
    if report.aggregate_status is not None:
        return report.aggregate_status
    if not report.pages:
        return "failed"

    page_statuses = {page.status for page in report.pages}
    for status in _STATUS_PRIORITY:
        if status in page_statuses:
            return status
    return "failed"


def _report_needs_repair(report: ValidatorReport) -> bool:
    return _resolved_aggregate_status(report) != "pass"


def _latest_validator_report(task_dir: Path) -> ValidatorReport:
    versioned_reports: list[tuple[int, Path]] = []
    for path in (task_dir / "reports").glob("validator.v*.json"):
        match = _VALIDATOR_REPORT_PATTERN.match(path.name)
        if match:
            versioned_reports.append((int(match.group(1)), path))

    if not versioned_reports:
        raise FileNotFoundError(
            f"No validator reports found in {task_dir / 'reports'} for task {task_dir}"
        )
    latest_report = max(versioned_reports, key=lambda report: report[0])[1]
    return ValidatorReport.model_validate_json(
        latest_report.read_text(encoding="utf-8")
    )


def _slide_model_path(task_dir: Path, attempt: int) -> Path:
    return task_dir / "slides" / f"slide-model.v{attempt}.json"


def _candidate_path(task_dir: Path, attempt: int) -> Path:
    return task_dir / "output" / f"candidate.v{attempt}.pptx"


def _runner_report_path(task_dir: Path, attempt: int) -> Path:
    return task_dir / "reports" / f"runner-repair.v{attempt}.json"


def _validator_report_path(task_dir: Path, attempt: int) -> Path:
    return task_dir / "reports" / f"validator.v{attempt}.json"


def _load_slide_model(task_dir: Path, attempt: int) -> SlideModel:
    return SlideModel.model_validate_json(
        _slide_model_path(task_dir, attempt).read_text(encoding="utf-8")
    )


def _latest_slide_model_attempt(task_dir: Path, *, max_attempt: int | None = None) -> int:
    versioned_models: list[tuple[int, Path]] = []
    for path in (task_dir / "slides").glob("slide-model.v*.json"):
        match = _SLIDE_MODEL_PATTERN.match(path.name)
        if not match:
            continue
        attempt = int(match.group(1))
        if max_attempt is not None and attempt > max_attempt:
            continue
        versioned_models.append((attempt, path))

    if not versioned_models:
        raise FileNotFoundError(
            f"No slide models found in {task_dir / 'slides'} for task {task_dir}"
        )
    return max(versioned_models, key=lambda model: model[0])[0]


def _write_final_artifacts(task_dir: Path, attempt: int) -> None:
    final_model = _load_slide_model(task_dir, attempt)
    (task_dir / "slides" / f"slide-model.final.v{attempt}.json").write_text(
        final_model.model_dump_json(indent=2),
        encoding="utf-8",
    )
    generate_pptx(final_model, task_dir / "output" / "final.pptx", asset_root=task_dir)


def _repair_until_pass_or_attempt_limit(
    task_dir: Path, initial_report: ValidatorReport
) -> ValidatorReport:
    max_attempts = _repair_attempt_limit(task_dir)
    report = initial_report
    while _report_needs_repair(report) and report.attempt < max_attempts:
        previous_attempt = report.attempt
        _run_repair(task_dir)
        report = _latest_validator_report(task_dir)
        if report.attempt <= previous_attempt:
            raise RuntimeError(
                "Repair did not produce a newer validator report after "
                f"attempt {previous_attempt}"
            )
    return report


def _semantic_table_repair_final_attempt(task_dir: Path, source_attempt: int) -> int:
    repair_result = upgrade_semantic_tables_with_guard(
        task_dir, source_attempt=source_attempt
    )
    if repair_result["status"] == "accepted":
        return int(repair_result["target_attempt"])
    return source_attempt


def _require_artifacts(label: str, paths: list[Path]) -> None:
    missing = [path for path in paths if not path.is_file()]
    if missing:
        missing_text = ", ".join(str(path) for path in missing)
        raise RuntimeError(f"{label} did not produce required artifact(s): {missing_text}")


def _require_runner_repair_artifacts(task_dir: Path, target_attempt: int) -> None:
    _require_artifacts(
        "Runner repair",
        [
            _slide_model_path(task_dir, target_attempt),
            _candidate_path(task_dir, target_attempt),
            _runner_report_path(task_dir, target_attempt),
        ],
    )


def _require_validator_repair_report(task_dir: Path, target_attempt: int) -> None:
    report_path = _validator_report_path(task_dir, target_attempt)
    if not report_path.is_file():
        raise RuntimeError(
            f"Validator repair did not produce required report: {report_path}"
        )
    report = ValidatorReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    if report.attempt != target_attempt:
        raise RuntimeError(
            f"Validator repair report {report_path} has attempt {report.attempt}; "
            f"expected {target_attempt}"
        )


def _write_agent_log(path: Path, result: subprocess.CompletedProcess[str]) -> None:
    path.write_text(
        f"returncode: {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}\n",
        encoding="utf-8",
    )


def _timeout_stream_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _write_agent_timeout_log(path: Path, exc: subprocess.TimeoutExpired) -> None:
    path.write_text(
        f"timeout_after_seconds: {exc.timeout}\n"
        f"stdout:\n{_timeout_stream_text(exc.output)}\n"
        f"stderr:\n{_timeout_stream_text(exc.stderr)}\n",
        encoding="utf-8",
    )


def _append_agent_log(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def _run_agent_with_log(
    invocation: CodexInvocation, message: str, log_path: Path
) -> subprocess.CompletedProcess[str]:
    try:
        result = run_codex_agent(invocation, message)
    except subprocess.TimeoutExpired as exc:
        _write_agent_timeout_log(log_path, exc)
        raise RuntimeError(
            f"{invocation.role.title()} repair timed out after {exc.timeout} seconds"
        ) from exc
    _write_agent_log(log_path, result)
    return result


def _run_deterministic_runner_fallback(
    task_dir: Path,
    *,
    source_attempt: int,
    target_attempt: int,
    reason: str,
    log_path: Path,
) -> None:
    result = run_deterministic_runner_repair(
        task_dir,
        source_attempt=source_attempt,
        target_attempt=target_attempt,
        reason=reason,
    )
    _append_agent_log(
        log_path,
        "\n--- deterministic runner fallback ---\n"
        f"{result}\n",
    )
    _require_runner_repair_artifacts(task_dir, target_attempt)


def _run_deterministic_validator_fallback(
    task_dir: Path,
    *,
    target_attempt: int,
    reason: str,
    log_path: Path,
) -> None:
    report = validate_candidate(task_dir, attempt=target_attempt)
    _append_agent_log(
        log_path,
        "\n--- deterministic validator fallback ---\n"
        f"reason: {reason}\n"
        f"aggregate_status: {report.aggregate_status}\n",
    )
    _require_validator_repair_report(task_dir, target_attempt)


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
    source_attempt = _latest_validator_report(task_dir).attempt
    target_attempt = source_attempt + 1

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
        "pass, perform a no-op repair by copying the latest slide model to the "
        "required target version, generating the required target PPTX, writing "
        "the repair report/event with the reason, and exiting without looping.\n\n"
        f"Required output contract for this pass: read attempt {source_attempt} "
        f"and write exactly slides/slide-model.v{target_attempt}.json, "
        f"output/candidate.v{target_attempt}.pptx, and "
        f"reports/runner-repair.v{target_attempt}.json. The workflow will treat "
        "a zero exit without those files as failure.\n\n"
        f"{_agent_tool_context()}"
    )
    runner_log_path = logs_dir / "runner-repair.log"
    try:
        runner_result = _run_agent_with_log(
            _codex_invocation("runner", task_dir),
            runner_message,
            runner_log_path,
        )
    except RuntimeError as exc:
        _run_deterministic_runner_fallback(
            task_dir,
            source_attempt=source_attempt,
            target_attempt=target_attempt,
            reason=f"runner_timeout: {exc}",
            log_path=runner_log_path,
        )
    else:
        if runner_result.returncode != 0:
            raise RuntimeError(
                f"Runner repair failed with return code {runner_result.returncode}"
            )
        try:
            _require_runner_repair_artifacts(task_dir, target_attempt)
        except RuntimeError as exc:
            _run_deterministic_runner_fallback(
                task_dir,
                source_attempt=source_attempt,
                target_attempt=target_attempt,
                reason=f"runner_missing_artifacts: {exc}",
                log_path=runner_log_path,
            )

    validator_message = (
        "Please validate every page after repair. Read task-manifest.json, the "
        "latest slides/slide-model.v*.json, the latest PPTX candidate, renders, "
        "and repair evidence, then write reports/validator.vN.json as strict "
        "valid JSON.\n\n"
        f"Required output contract for this pass: validate "
        f"output/candidate.v{target_attempt}.pptx against "
        f"slides/slide-model.v{target_attempt}.json and write exactly "
        f"reports/validator.v{target_attempt}.json with attempt "
        f"{target_attempt}. The workflow will treat a zero exit without that "
        "report as failure.\n\n"
        f"{_agent_tool_context()}"
    )
    validator_log_path = logs_dir / "validator-repair.log"
    try:
        validator_result = _run_agent_with_log(
            _codex_invocation("validator", task_dir),
            validator_message,
            validator_log_path,
        )
    except RuntimeError as exc:
        _run_deterministic_validator_fallback(
            task_dir,
            target_attempt=target_attempt,
            reason=f"validator_timeout: {exc}",
            log_path=validator_log_path,
        )
    else:
        if validator_result.returncode != 0:
            _run_deterministic_validator_fallback(
                task_dir,
                target_attempt=target_attempt,
                reason=f"validator_returncode_{validator_result.returncode}",
                log_path=validator_log_path,
            )
            return
        try:
            _require_validator_repair_report(task_dir, target_attempt)
        except RuntimeError as exc:
            _run_deterministic_validator_fallback(
                task_dir,
                target_attempt=target_attempt,
                reason=f"validator_missing_report: {exc}",
                log_path=validator_log_path,
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
    report = validate_candidate(task_dir, attempt=1)
    report = _repair_until_pass_or_attempt_limit(task_dir, report)
    final_attempt = _latest_slide_model_attempt(task_dir, max_attempt=report.attempt)
    final_attempt = _semantic_table_repair_final_attempt(task_dir, final_attempt)
    _write_final_artifacts(task_dir, final_attempt)


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
