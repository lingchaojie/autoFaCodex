import json
from pathlib import Path
import shutil

from autofacodex.contracts import ValidatorReport
from autofacodex.workflows.pdf_to_ppt import run_pdf_to_ppt


def discover_pdfs(samples_dir: Path) -> list[Path]:
    return sorted(
        path for path in samples_dir.glob("*.pdf") if not path.name.startswith("~$")
    )


def _latest_validator_report(task_dir: Path) -> ValidatorReport:
    reports = sorted((task_dir / "reports").glob("validator.v*.json"))
    if not reports:
        raise FileNotFoundError(
            f"No validator reports found in {task_dir / 'reports'} for task {task_dir}"
        )
    return ValidatorReport.model_validate_json(reports[-1].read_text(encoding="utf-8"))


def _issue_counts(reports: list[ValidatorReport]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for report in reports:
        for page in report.pages:
            for issue in page.issues:
                counts[issue.type] = counts.get(issue.type, 0) + 1
    return dict(sorted(counts.items()))


def write_evaluation_summary(task_dirs: list[Path], output_root: Path) -> Path:
    reports = [_latest_validator_report(task_dir) for task_dir in task_dirs]
    pages = [page for report in reports for page in report.pages]
    status_counts = {
        "pass": 0,
        "repair_needed": 0,
        "manual_review": 0,
        "failed": 0,
    }
    for report in reports:
        if report.aggregate_status is not None:
            status_counts[report.aggregate_status] += 1

    summary = {
        "sample_count": len(reports),
        "page_count": len(pages),
        "average_visual_score": round(
            sum(page.visual_score for page in pages) / len(pages), 4
        )
        if pages
        else 0.0,
        "min_visual_score": round(min(page.visual_score for page in pages), 4)
        if pages
        else 0.0,
        "aggregate_status_counts": status_counts,
        "issue_counts": _issue_counts(reports),
        "samples": [
            {
                "task_dir": str(task_dir),
                "task_id": report.task_id,
                "aggregate_status": report.aggregate_status,
                "page_count": len(report.pages),
                "average_visual_score": round(
                    sum(page.visual_score for page in report.pages) / len(report.pages),
                    4,
                )
                if report.pages
                else 0.0,
                "min_visual_score": round(
                    min(page.visual_score for page in report.pages), 4
                )
                if report.pages
                else 0.0,
            }
            for task_dir, report in zip(task_dirs, reports)
        ],
    }
    summary_path = output_root / "evaluation-summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary_path


def run_samples(samples_dir: Path, output_root: Path) -> list[Path]:
    output_root.mkdir(parents=True, exist_ok=True)

    task_dirs: list[Path] = []
    for index, pdf_path in enumerate(discover_pdfs(samples_dir), start=1):
        task_dir = output_root / f"sample-{index:03d}-{pdf_path.stem}"
        if task_dir.exists():
            shutil.rmtree(task_dir)
        task_dir.mkdir(parents=True)
        shutil.copy2(pdf_path, task_dir / "input.pdf")
        try:
            run_pdf_to_ppt(task_dir)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to run sample {pdf_path} in task dir {task_dir}"
            ) from exc
        task_dirs.append(task_dir)

    write_evaluation_summary(task_dirs, output_root)
    return task_dirs


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run PDF to PPT conversion over sample PDFs."
    )
    parser.add_argument(
        "samples_dir", nargs="?", type=Path, default=Path("pdf-to-ppt-test-samples")
    )
    parser.add_argument(
        "output_root", nargs="?", type=Path, default=Path("shared-tasks/evaluation")
    )
    args = parser.parse_args()
    run_samples(args.samples_dir, args.output_root)


if __name__ == "__main__":
    main()
