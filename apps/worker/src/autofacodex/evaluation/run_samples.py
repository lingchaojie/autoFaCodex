from pathlib import Path
import shutil

from autofacodex.workflows.pdf_to_ppt import run_pdf_to_ppt


def discover_pdfs(samples_dir: Path) -> list[Path]:
    return sorted(
        path for path in samples_dir.glob("*.pdf") if not path.name.startswith("~$")
    )


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

    return task_dirs


def main() -> None:
    run_samples(Path("pdf-to-ppt-test-samples"), Path("shared-tasks/evaluation"))


if __name__ == "__main__":
    main()
