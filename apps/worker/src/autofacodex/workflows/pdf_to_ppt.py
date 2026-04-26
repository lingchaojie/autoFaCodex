from pathlib import Path


def run_pdf_to_ppt(task_dir: Path) -> None:
    (task_dir / "logs").mkdir(exist_ok=True)
    (task_dir / "logs" / "workflow.log").write_text("pdf_to_ppt workflow started\n", encoding="utf-8")
