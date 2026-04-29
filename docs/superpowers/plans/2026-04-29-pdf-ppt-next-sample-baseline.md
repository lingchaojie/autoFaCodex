# PDF PPT Next Sample Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run baseline conversion and ideal-PPTX comparison for the two non-Maple samples, then recommend the next PDF-to-PPT improvement target from measured evidence.

**Architecture:** This is an evidence-generation pass, not a product-code change. Each sample gets an isolated task directory under `shared-tasks/`; the existing workflow creates PPTX and validator reports, the existing ideal comparison tool creates structure deltas, and an archive document records the ranking decision.

**Tech Stack:** Python 3.10/3.11, existing `apps/worker/.venv`, PyMuPDF, python-pptx, LibreOffice, `autofacodex.workflows.pdf_to_ppt`, `autofacodex.evaluation.compare_ideal_pptx`, pytest, Vitest.

---

## File Map

- Read: `/home/alvin/AutoFaCodex/pdf-to-ppt/pdf-source/清博空天BP Final.pdf`
- Read: `/home/alvin/AutoFaCodex/pdf-to-ppt/pdf-source/20260110.无穹创新BP_v27-仅供隐山资本参考.pdf`
- Read: `/home/alvin/AutoFaCodex/pdf-to-ppt/example-output/清博空天BP Final.pptx`
- Read: `/home/alvin/AutoFaCodex/pdf-to-ppt/example-output/20260110.无穹创新BP_v27-仅供隐山资本参考.pptx`
- Create: `shared-tasks/next-baseline-qingbo-20260429/`
- Create: `shared-tasks/next-baseline-wuqiong-20260429/`
- Create: `shared-tasks/next-baseline-qingbo-20260429/reports/ideal-comparison.json`
- Create: `shared-tasks/next-baseline-wuqiong-20260429/reports/ideal-comparison.json`
- Create: `docs/superpowers/archives/2026-04-29-pdf-ppt-next-sample-baseline-results.md`

No application source files should be modified in this baseline pass unless a pipeline failure blocks both samples and is confirmed as a regression.

## Task 1: Verify Inputs And Baseline Environment

**Files:**
- Read: `/home/alvin/AutoFaCodex/pdf-to-ppt/pdf-source/*.pdf`
- Read: `/home/alvin/AutoFaCodex/pdf-to-ppt/example-output/*.pptx`

- [ ] **Step 1: Confirm sample and ideal files exist**

Run:

```bash
test -f "/home/alvin/AutoFaCodex/pdf-to-ppt/pdf-source/清博空天BP Final.pdf"
test -f "/home/alvin/AutoFaCodex/pdf-to-ppt/pdf-source/20260110.无穹创新BP_v27-仅供隐山资本参考.pdf"
test -f "/home/alvin/AutoFaCodex/pdf-to-ppt/example-output/清博空天BP Final.pptx"
test -f "/home/alvin/AutoFaCodex/pdf-to-ppt/example-output/20260110.无穹创新BP_v27-仅供隐山资本参考.pptx"
```

Expected: all four commands exit `0`.

- [ ] **Step 2: Confirm task directories are not already present**

Run:

```bash
test ! -e shared-tasks/next-baseline-qingbo-20260429
test ! -e shared-tasks/next-baseline-wuqiong-20260429
```

Expected: both commands exit `0`. If either path exists, stop and report the existing path instead of deleting it.

- [ ] **Step 3: Verify worktree baseline tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest -q
```

Expected: `212 passed, 5 warnings`.

Run:

```bash
npm --workspace apps/web run test -- --run
```

Expected: `9` test files and `41` tests pass.

- [ ] **Step 4: Commit status checkpoint**

Run:

```bash
git status --short
```

Expected: no tracked or untracked changes from this task.

## Task 2: Run Qingbo Baseline

**Files:**
- Read: `/home/alvin/AutoFaCodex/pdf-to-ppt/pdf-source/清博空天BP Final.pdf`
- Read: `/home/alvin/AutoFaCodex/pdf-to-ppt/example-output/清博空天BP Final.pptx`
- Create: `shared-tasks/next-baseline-qingbo-20260429/`
- Create: `shared-tasks/next-baseline-qingbo-20260429/reports/ideal-comparison.json`

- [ ] **Step 1: Create task directory and copy input PDF**

Run:

```bash
mkdir -p shared-tasks/next-baseline-qingbo-20260429
cp "/home/alvin/AutoFaCodex/pdf-to-ppt/pdf-source/清博空天BP Final.pdf" shared-tasks/next-baseline-qingbo-20260429/input.pdf
```

Expected: `shared-tasks/next-baseline-qingbo-20260429/input.pdf` exists.

- [ ] **Step 2: Run PDF-to-PPT workflow**

Run:

```bash
TASK_DIR=shared-tasks/next-baseline-qingbo-20260429 \
CODEX_AGENT_TIMEOUT_SECONDS=120 \
PYTHONPATH=apps/worker/src \
apps/worker/.venv/bin/python - <<'PY'
import os
from pathlib import Path

from autofacodex.workflows.pdf_to_ppt import run_pdf_to_ppt

run_pdf_to_ppt(Path(os.environ["TASK_DIR"]))
PY
```

Expected: command exits `0` and writes `output/final.pptx`, at least one `reports/validator.v*.json`, and workflow diagnostics under the task directory.

- [ ] **Step 3: Generate Qingbo ideal comparison**

Run:

```bash
TASK_DIR=shared-tasks/next-baseline-qingbo-20260429 \
IDEAL_PPTX="/home/alvin/AutoFaCodex/pdf-to-ppt/example-output/清博空天BP Final.pptx" \
PYTHONPATH=apps/worker/src \
apps/worker/.venv/bin/python - <<'PY'
import json
import os
from pathlib import Path

from autofacodex.evaluation.compare_ideal_pptx import compare_pptx_structure

task_dir = Path(os.environ["TASK_DIR"])
ideal_pptx = Path(os.environ["IDEAL_PPTX"])
report = compare_pptx_structure(task_dir / "output" / "final.pptx", ideal_pptx)
output_path = task_dir / "reports" / "ideal-comparison.json"
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(
    json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(output_path)
PY
```

Expected: command exits `0` and prints `shared-tasks/next-baseline-qingbo-20260429/reports/ideal-comparison.json`.

- [ ] **Step 4: Inspect Qingbo summary**

Run:

```bash
TASK_DIR=shared-tasks/next-baseline-qingbo-20260429 \
PYTHONPATH=apps/worker/src \
apps/worker/.venv/bin/python - <<'PY'
import json
import os
import re
from pathlib import Path

from autofacodex.contracts import ValidatorReport

task_dir = Path(os.environ["TASK_DIR"])
reports = []
for path in (task_dir / "reports").glob("validator.v*.json"):
    match = re.match(r"validator\.v(\d+)\.json$", path.name)
    if match:
        reports.append((int(match.group(1)), path))
latest = max(reports)[1]
validator = ValidatorReport.model_validate_json(latest.read_text(encoding="utf-8"))
ideal = json.loads((task_dir / "reports" / "ideal-comparison.json").read_text(encoding="utf-8"))
status_counts = {}
for page in validator.pages:
    status_counts[page.status] = status_counts.get(page.status, 0) + 1
pages = [
    {
        "page": page.page_number,
        "status": page.status,
        "visual": round(page.visual_score, 4),
        "editable": page.editable_score,
        "text": page.text_coverage_score,
        "raster": round(page.raster_fallback_ratio, 4),
        "issues": [issue.type for issue in page.issues],
    }
    for page in validator.pages
]
top_deltas = sorted(
    ideal["pages"],
    key=lambda page: (
        abs(page.get("picture_count_delta", 0))
        + abs(page.get("shape_count_delta", 0))
        + abs(page.get("text_box_count_delta", 0))
    ),
    reverse=True,
)[:5]
print(json.dumps({
    "sample": "qingbo",
    "latest_validator": latest.name,
    "aggregate_status": validator.aggregate_status,
    "status_counts": status_counts,
    "average_visual": round(sum(page.visual_score for page in validator.pages) / len(validator.pages), 4),
    "min_visual": round(min(page.visual_score for page in validator.pages), 4),
    "pages": pages,
    "top_structure_deltas": top_deltas,
}, indent=2, ensure_ascii=False))
PY
```

Expected: command exits `0` and prints a JSON summary for Qingbo.

- [ ] **Step 5: Commit generated Qingbo evidence if task artifacts are tracked by this branch**

Run:

```bash
git status --short shared-tasks/next-baseline-qingbo-20260429
```

Expected: if no output appears, `shared-tasks/` is ignored and there is nothing to commit for task artifacts. If output appears, stop and report the tracked artifact paths before committing.

## Task 3: Run Wuqiong Baseline

**Files:**
- Read: `/home/alvin/AutoFaCodex/pdf-to-ppt/pdf-source/20260110.无穹创新BP_v27-仅供隐山资本参考.pdf`
- Read: `/home/alvin/AutoFaCodex/pdf-to-ppt/example-output/20260110.无穹创新BP_v27-仅供隐山资本参考.pptx`
- Create: `shared-tasks/next-baseline-wuqiong-20260429/`
- Create: `shared-tasks/next-baseline-wuqiong-20260429/reports/ideal-comparison.json`

- [ ] **Step 1: Create task directory and copy input PDF**

Run:

```bash
mkdir -p shared-tasks/next-baseline-wuqiong-20260429
cp "/home/alvin/AutoFaCodex/pdf-to-ppt/pdf-source/20260110.无穹创新BP_v27-仅供隐山资本参考.pdf" shared-tasks/next-baseline-wuqiong-20260429/input.pdf
```

Expected: `shared-tasks/next-baseline-wuqiong-20260429/input.pdf` exists.

- [ ] **Step 2: Run PDF-to-PPT workflow**

Run:

```bash
TASK_DIR=shared-tasks/next-baseline-wuqiong-20260429 \
CODEX_AGENT_TIMEOUT_SECONDS=120 \
PYTHONPATH=apps/worker/src \
apps/worker/.venv/bin/python - <<'PY'
import os
from pathlib import Path

from autofacodex.workflows.pdf_to_ppt import run_pdf_to_ppt

run_pdf_to_ppt(Path(os.environ["TASK_DIR"]))
PY
```

Expected: command exits `0` and writes `output/final.pptx`, at least one `reports/validator.v*.json`, and workflow diagnostics under the task directory.

- [ ] **Step 3: Generate Wuqiong ideal comparison**

Run:

```bash
TASK_DIR=shared-tasks/next-baseline-wuqiong-20260429 \
IDEAL_PPTX="/home/alvin/AutoFaCodex/pdf-to-ppt/example-output/20260110.无穹创新BP_v27-仅供隐山资本参考.pptx" \
PYTHONPATH=apps/worker/src \
apps/worker/.venv/bin/python - <<'PY'
import json
import os
from pathlib import Path

from autofacodex.evaluation.compare_ideal_pptx import compare_pptx_structure

task_dir = Path(os.environ["TASK_DIR"])
ideal_pptx = Path(os.environ["IDEAL_PPTX"])
report = compare_pptx_structure(task_dir / "output" / "final.pptx", ideal_pptx)
output_path = task_dir / "reports" / "ideal-comparison.json"
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(
    json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(output_path)
PY
```

Expected: command exits `0` and prints `shared-tasks/next-baseline-wuqiong-20260429/reports/ideal-comparison.json`.

- [ ] **Step 4: Inspect Wuqiong summary**

Run:

```bash
TASK_DIR=shared-tasks/next-baseline-wuqiong-20260429 \
PYTHONPATH=apps/worker/src \
apps/worker/.venv/bin/python - <<'PY'
import json
import os
import re
from pathlib import Path

from autofacodex.contracts import ValidatorReport

task_dir = Path(os.environ["TASK_DIR"])
reports = []
for path in (task_dir / "reports").glob("validator.v*.json"):
    match = re.match(r"validator\.v(\d+)\.json$", path.name)
    if match:
        reports.append((int(match.group(1)), path))
latest = max(reports)[1]
validator = ValidatorReport.model_validate_json(latest.read_text(encoding="utf-8"))
ideal = json.loads((task_dir / "reports" / "ideal-comparison.json").read_text(encoding="utf-8"))
status_counts = {}
for page in validator.pages:
    status_counts[page.status] = status_counts.get(page.status, 0) + 1
pages = [
    {
        "page": page.page_number,
        "status": page.status,
        "visual": round(page.visual_score, 4),
        "editable": page.editable_score,
        "text": page.text_coverage_score,
        "raster": round(page.raster_fallback_ratio, 4),
        "issues": [issue.type for issue in page.issues],
    }
    for page in validator.pages
]
top_deltas = sorted(
    ideal["pages"],
    key=lambda page: (
        abs(page.get("picture_count_delta", 0))
        + abs(page.get("shape_count_delta", 0))
        + abs(page.get("text_box_count_delta", 0))
    ),
    reverse=True,
)[:5]
print(json.dumps({
    "sample": "wuqiong",
    "latest_validator": latest.name,
    "aggregate_status": validator.aggregate_status,
    "status_counts": status_counts,
    "average_visual": round(sum(page.visual_score for page in validator.pages) / len(validator.pages), 4),
    "min_visual": round(min(page.visual_score for page in validator.pages), 4),
    "pages": pages,
    "top_structure_deltas": top_deltas,
}, indent=2, ensure_ascii=False))
PY
```

Expected: command exits `0` and prints a JSON summary for Wuqiong.

- [ ] **Step 5: Commit generated Wuqiong evidence if task artifacts are tracked by this branch**

Run:

```bash
git status --short shared-tasks/next-baseline-wuqiong-20260429
```

Expected: if no output appears, `shared-tasks/` is ignored and there is nothing to commit for task artifacts. If output appears, stop and report the tracked artifact paths before committing.

## Task 4: Rank Samples And Archive Results

**Files:**
- Read: `shared-tasks/next-baseline-qingbo-20260429/reports/validator.v*.json`
- Read: `shared-tasks/next-baseline-qingbo-20260429/reports/ideal-comparison.json`
- Read: `shared-tasks/next-baseline-wuqiong-20260429/reports/validator.v*.json`
- Read: `shared-tasks/next-baseline-wuqiong-20260429/reports/ideal-comparison.json`
- Create: `docs/superpowers/archives/2026-04-29-pdf-ppt-next-sample-baseline-results.md`

- [ ] **Step 1: Generate combined ranking JSON**

Run:

```bash
PYTHONPATH=apps/worker/src \
apps/worker/.venv/bin/python - <<'PY'
import json
import re
from pathlib import Path

from autofacodex.contracts import ValidatorReport

samples = [
    ("qingbo", "清博空天BP Final", Path("shared-tasks/next-baseline-qingbo-20260429")),
    ("wuqiong", "20260110.无穹创新BP_v27-仅供隐山资本参考", Path("shared-tasks/next-baseline-wuqiong-20260429")),
]

def latest_validator(task_dir: Path) -> tuple[Path, ValidatorReport]:
    versioned = []
    for path in (task_dir / "reports").glob("validator.v*.json"):
        match = re.match(r"validator\.v(\d+)\.json$", path.name)
        if match:
            versioned.append((int(match.group(1)), path))
    path = max(versioned)[1]
    return path, ValidatorReport.model_validate_json(path.read_text(encoding="utf-8"))

def status_counts(report: ValidatorReport) -> dict[str, int]:
    counts = {"pass": 0, "manual_review": 0, "repair_needed": 0, "failed": 0}
    for page in report.pages:
        counts[page.status] = counts.get(page.status, 0) + 1
    return counts

def top_structure_deltas(ideal: dict) -> list[dict]:
    return sorted(
        ideal["pages"],
        key=lambda page: (
            abs(page.get("picture_count_delta", 0))
            + abs(page.get("shape_count_delta", 0))
            + abs(page.get("text_box_count_delta", 0))
        ),
        reverse=True,
    )[:5]

summaries = []
for key, name, task_dir in samples:
    validator_path, validator = latest_validator(task_dir)
    ideal = json.loads((task_dir / "reports" / "ideal-comparison.json").read_text(encoding="utf-8"))
    pages = validator.pages
    candidate = {
        "key": key,
        "name": name,
        "task_dir": str(task_dir),
        "validator_report": str(validator_path),
        "aggregate_status": validator.aggregate_status,
        "status_counts": status_counts(validator),
        "page_count": len(pages),
        "average_visual": round(sum(page.visual_score for page in pages) / len(pages), 4),
        "min_visual": round(min(page.visual_score for page in pages), 4),
        "issue_counts": {},
        "raster_pages": [
            page.page_number
            for page in pages
            if page.raster_fallback_ratio > 0
        ],
        "low_visual_pages": [
            {
                "page": page.page_number,
                "status": page.status,
                "visual": round(page.visual_score, 4),
                "text": page.text_coverage_score,
                "editable": page.editable_score,
                "raster": round(page.raster_fallback_ratio, 4),
                "issues": [issue.type for issue in page.issues],
            }
            for page in sorted(pages, key=lambda page: page.visual_score)[:5]
        ],
        "top_structure_deltas": top_structure_deltas(ideal),
    }
    for page in pages:
        for issue in page.issues:
            candidate["issue_counts"][issue.type] = candidate["issue_counts"].get(issue.type, 0) + 1
    candidate["issue_counts"] = dict(sorted(candidate["issue_counts"].items()))
    summaries.append(candidate)

ranked = sorted(
    summaries,
    key=lambda item: (
        item["status_counts"].get("repair_needed", 0) + item["status_counts"].get("manual_review", 0),
        -item["min_visual"],
        -item["average_visual"],
        len(item["raster_pages"]),
    ),
    reverse=True,
)
print(json.dumps({"samples": summaries, "recommended_next_target": ranked[0]}, indent=2, ensure_ascii=False))
PY
```

Expected: command exits `0` and prints combined JSON with `samples` and `recommended_next_target`.

- [ ] **Step 2: Create archive document from the combined ranking**

Run:

```bash
PYTHONPATH=apps/worker/src \
apps/worker/.venv/bin/python - <<'PY'
import json
import re
from pathlib import Path

from autofacodex.contracts import ValidatorReport

archive_path = Path("docs/superpowers/archives/2026-04-29-pdf-ppt-next-sample-baseline-results.md")
samples = [
    ("qingbo", "清博空天BP Final", Path("shared-tasks/next-baseline-qingbo-20260429")),
    ("wuqiong", "20260110.无穹创新BP_v27-仅供隐山资本参考", Path("shared-tasks/next-baseline-wuqiong-20260429")),
]

def latest_validator(task_dir: Path) -> tuple[Path, ValidatorReport]:
    versioned = []
    for path in (task_dir / "reports").glob("validator.v*.json"):
        match = re.match(r"validator\.v(\d+)\.json$", path.name)
        if match:
            versioned.append((int(match.group(1)), path))
    path = max(versioned)[1]
    return path, ValidatorReport.model_validate_json(path.read_text(encoding="utf-8"))

def status_counts(report: ValidatorReport) -> dict[str, int]:
    counts = {"pass": 0, "manual_review": 0, "repair_needed": 0, "failed": 0}
    for page in report.pages:
        counts[page.status] = counts.get(page.status, 0) + 1
    return counts

def top_structure_deltas(ideal: dict) -> list[dict]:
    return sorted(
        ideal["pages"],
        key=lambda page: (
            abs(page.get("picture_count_delta", 0))
            + abs(page.get("shape_count_delta", 0))
            + abs(page.get("text_box_count_delta", 0))
        ),
        reverse=True,
    )[:5]

def issue_counts(report: ValidatorReport) -> dict[str, int]:
    counts = {}
    for page in report.pages:
        for issue in page.issues:
            counts[issue.type] = counts.get(issue.type, 0) + 1
    return dict(sorted(counts.items()))

summaries = []
for key, name, task_dir in samples:
    validator_path, validator = latest_validator(task_dir)
    ideal = json.loads((task_dir / "reports" / "ideal-comparison.json").read_text(encoding="utf-8"))
    pages = validator.pages
    summaries.append(
        {
            "key": key,
            "name": name,
            "task_dir": str(task_dir),
            "validator_report": str(validator_path),
            "aggregate_status": validator.aggregate_status,
            "status_counts": status_counts(validator),
            "page_count": len(pages),
            "average_visual": round(sum(page.visual_score for page in pages) / len(pages), 4),
            "min_visual": round(min(page.visual_score for page in pages), 4),
            "issue_counts": issue_counts(validator),
            "raster_pages": [page.page_number for page in pages if page.raster_fallback_ratio > 0],
            "low_visual_pages": [
                {
                    "page": page.page_number,
                    "status": page.status,
                    "visual": round(page.visual_score, 4),
                    "text": page.text_coverage_score,
                    "editable": page.editable_score,
                    "raster": round(page.raster_fallback_ratio, 4),
                    "issues": ", ".join(issue.type for issue in page.issues) or "none",
                }
                for page in sorted(pages, key=lambda page: page.visual_score)[:5]
            ],
            "top_structure_deltas": top_structure_deltas(ideal),
        }
    )

ranked = sorted(
    summaries,
    key=lambda item: (
        item["status_counts"].get("repair_needed", 0) + item["status_counts"].get("manual_review", 0),
        -item["min_visual"],
        -item["average_visual"],
        len(item["raster_pages"]),
    ),
    reverse=True,
)
target = ranked[0]

lines = [
    "# PDF PPT Next Sample Baseline Results",
    "",
    "Date: 2026-04-29",
    "",
    "## Inputs",
    "",
    "- Qingbo PDF: `/home/alvin/AutoFaCodex/pdf-to-ppt/pdf-source/清博空天BP Final.pdf`",
    "- Qingbo ideal PPTX: `/home/alvin/AutoFaCodex/pdf-to-ppt/example-output/清博空天BP Final.pptx`",
    "- Wuqiong PDF: `/home/alvin/AutoFaCodex/pdf-to-ppt/pdf-source/20260110.无穹创新BP_v27-仅供隐山资本参考.pdf`",
    "- Wuqiong ideal PPTX: `/home/alvin/AutoFaCodex/pdf-to-ppt/example-output/20260110.无穹创新BP_v27-仅供隐山资本参考.pptx`",
    "",
    "## Task Directories",
    "",
    "- Qingbo: `shared-tasks/next-baseline-qingbo-20260429`",
    "- Wuqiong: `shared-tasks/next-baseline-wuqiong-20260429`",
    "",
    "## Sample Summary",
    "",
    "| Sample | Aggregate | Pages | Pass | Manual Review | Repair Needed | Failed | Avg Visual | Min Visual | Issues | Raster Pages |",
    "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
]
for item in summaries:
    counts = item["status_counts"]
    issues = ", ".join(f"{name}:{count}" for name, count in item["issue_counts"].items()) or "none"
    raster_pages = ", ".join(str(page) for page in item["raster_pages"]) or "none"
    lines.append(
        f"| {item['name']} | {item['aggregate_status']} | {item['page_count']} | "
        f"{counts.get('pass', 0)} | {counts.get('manual_review', 0)} | "
        f"{counts.get('repair_needed', 0)} | {counts.get('failed', 0)} | "
        f"{item['average_visual']:.4f} | {item['min_visual']:.4f} | {issues} | {raster_pages} |"
    )

for item in summaries:
    lines.extend(
        [
            "",
            f"## {item['name']} Lowest Visual Pages",
            "",
            "| Page | Status | Visual | Text | Editable | Raster | Issues |",
            "| ---: | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for page in item["low_visual_pages"]:
        lines.append(
            f"| {page['page']} | {page['status']} | {page['visual']:.4f} | "
            f"{page['text']} | {page['editable']} | {page['raster']:.4f} | {page['issues']} |"
        )
    lines.extend(
        [
            "",
            f"## {item['name']} Largest Structure Deltas",
            "",
            "| Page | Generated Strategy | Ideal Strategy | Picture Delta | Shape Delta | Text Box Delta | Picture Coverage Delta |",
            "| ---: | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for page in item["top_structure_deltas"]:
        lines.append(
            f"| {page['page_number']} | {page['generated_strategy']} | {page['ideal_strategy']} | "
            f"{page.get('picture_count_delta', 0)} | {page.get('shape_count_delta', 0)} | "
            f"{page.get('text_box_count_delta', 0)} | {page.get('picture_coverage_ratio_delta', 0):.6f} |"
        )

first_pages = ", ".join(str(page["page"]) for page in target["low_visual_pages"][:3])
lines.extend(
    [
        "",
        "## Recommendation",
        "",
        f"Recommended next target: `{target['name']}`.",
        "",
        f"First problem pages to inspect: {first_pages}.",
        "",
        "Reason: this sample ranks highest by combined manual-review/repair-needed page count, minimum visual score, average visual score, raster fallback pages, and generated-vs-ideal structure deltas.",
        "",
        "## Verification Commands And Results",
        "",
        "- `cd apps/worker && .venv/bin/pytest -q`",
        "  - Result: final worker verification result is added in Task 5 Step 3.",
        "- `npm --workspace apps/web run test -- --run`",
        "  - Result: final web verification result is added in Task 5 Step 3.",
        "- Qingbo workflow command from Task 2 Step 2",
        "  - Result: exited `0`, wrote `output/final.pptx` and validator reports.",
        "- Qingbo ideal comparison command from Task 2 Step 3",
        "  - Result: exited `0`, wrote `reports/ideal-comparison.json`.",
        "- Wuqiong workflow command from Task 3 Step 2",
        "  - Result: exited `0`, wrote `output/final.pptx` and validator reports.",
        "- Wuqiong ideal comparison command from Task 3 Step 3",
        "  - Result: exited `0`, wrote `reports/ideal-comparison.json`.",
        "",
    ]
)
archive_path.parent.mkdir(parents=True, exist_ok=True)
archive_path.write_text("\n".join(lines), encoding="utf-8")
print(archive_path)
PY
```

Expected: command exits `0` and prints `docs/superpowers/archives/2026-04-29-pdf-ppt-next-sample-baseline-results.md`.

- [ ] **Step 3: Review archive against raw JSON**

Run:

```bash
test -f docs/superpowers/archives/2026-04-29-pdf-ppt-next-sample-baseline-results.md
test -f shared-tasks/next-baseline-qingbo-20260429/reports/ideal-comparison.json
test -f shared-tasks/next-baseline-wuqiong-20260429/reports/ideal-comparison.json
```

Expected: all three commands exit `0`.

Manually compare the archive recommendation against the JSON printed in Step 1. If the archive selects a different target than `recommended_next_target`, revise the archive before proceeding.

## Task 5: Final Verification And Commit

**Files:**
- Modify: `docs/superpowers/archives/2026-04-29-pdf-ppt-next-sample-baseline-results.md`

- [ ] **Step 1: Run worker suite**

Run:

```bash
cd apps/worker && .venv/bin/pytest -q
```

Expected: `212 passed, 5 warnings`.

- [ ] **Step 2: Run web suite**

Run:

```bash
npm --workspace apps/web run test -- --run
```

Expected: `9` test files and `41` tests pass.

- [ ] **Step 3: Update final verification results in the archive**

After Step 1 and Step 2 pass, update these two lines in `docs/superpowers/archives/2026-04-29-pdf-ppt-next-sample-baseline-results.md`:

```markdown
- `cd apps/worker && .venv/bin/pytest -q`
  - Result: `212 passed, 5 warnings`
- `npm --workspace apps/web run test -- --run`
  - Result: `9 passed` test files, `41 passed` tests
```

Expected: the archive records the exact final verification counts.

- [ ] **Step 4: Check whitespace and status**

Run:

```bash
git diff --check
git status --short
```

Expected: `git diff --check` exits `0`. `git status --short` shows only `docs/superpowers/archives/2026-04-29-pdf-ppt-next-sample-baseline-results.md` unless shared task artifacts are intentionally tracked.

- [ ] **Step 5: Commit archive**

Run:

```bash
git add docs/superpowers/archives/2026-04-29-pdf-ppt-next-sample-baseline-results.md
git commit -m "docs: archive next sample baseline"
```

Expected: commit succeeds.

- [ ] **Step 6: Report next target**

Run:

```bash
git log --oneline --max-count=3
git status --short --branch
```

Expected: latest commit is `docs: archive next sample baseline` and worktree is clean. Report the recommended next target, first problem pages, task directories, and verification results.
