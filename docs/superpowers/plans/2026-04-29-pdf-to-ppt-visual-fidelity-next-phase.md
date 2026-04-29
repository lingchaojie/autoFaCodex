# PDF To PPT Visual Fidelity Next Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move PDF-to-PPT repair attempts from `manual_review` toward `pass` by adding region-level visual evidence, constrained repair actions, and sample-wide regression reporting against both source PDFs and ideal PPTX references.

**Architecture:** Keep the existing deterministic conversion pipeline, but make repair decisions data-driven. Validator produces page-local issue regions and structured repair hints; Runner chooses from a small set of deterministic repair actions; each action writes a new slide model attempt, generates a PPTX, and lets Validator re-score from rendered evidence.

**Tech Stack:** Python 3.11, Pydantic, PyMuPDF, python-pptx, Pillow, scikit-image, LibreOffice, pytest, jq-compatible JSON reports, existing Runner/Validator agent assets.

---

## File Map

- Modify `apps/worker/src/autofacodex/contracts.py`: add optional region evidence and structured repair hints to `ValidatorIssue`.
- Modify `apps/worker/tests/test_contracts.py`: cover region evidence and strict validation.
- Modify `apps/worker/src/autofacodex/tools/visual_diff.py`: add connected-component issue-region extraction from diff images.
- Create `apps/worker/tests/test_visual_diff_regions.py`: cover diff mask to normalized region extraction.
- Modify `apps/worker/src/autofacodex/tools/validate_candidate.py`: attach page-local issue regions and action hints to visual fidelity issues.
- Modify `apps/worker/tests/test_validate_candidate.py`: cover visual issue regions and manual-review/pass thresholds.
- Create `apps/worker/src/autofacodex/tools/repair_actions.py`: implement constrained slide-model repair actions.
- Create `apps/worker/tests/test_repair_actions.py`: cover bbox adjustment, z-order normalization, background marking, and no-op behavior.
- Modify `apps/worker/src/autofacodex/tools/runner_repair.py`: use Validator regions and `repair_actions.py` before falling back to background-only repair.
- Modify `apps/worker/tests/test_runner_repair.py`: cover region-directed repair action selection.
- Modify `apps/worker/src/autofacodex/tools/pptx_inspect.py`: expose image, text, shape, and table bounding boxes per slide.
- Modify `apps/worker/tests/test_pptx_inspect.py`: cover geometry extraction from generated PPTX fixtures.
- Create `apps/worker/src/autofacodex/evaluation/compare_ideal_pptx.py`: compare generated PPTX structure against ideal PPTX references.
- Create `apps/worker/tests/test_compare_ideal_pptx.py`: cover text-run counts, object counts, background ratio, and page alignment.
- Modify `apps/worker/src/autofacodex/evaluation/run_samples.py`: include ideal-PPT comparison fields and before/after repair deltas.
- Modify `apps/worker/tests/test_sample_discovery.py`: cover sample report schema with ideal comparison.
- Modify `apps/worker/agent_assets/runner/runner.system.md`: require constrained repair-action usage.
- Modify `apps/worker/agent_assets/runner/SKILL.md`: document action selection and no-op fallback.
- Modify `apps/worker/agent_assets/validator/validator.system.md`: require region evidence and action hints.
- Modify `apps/worker/agent_assets/validator/SKILL.md`: document region extraction and structured repair hints.
- Modify `apps/worker/tests/test_agent_assets.py`: assert prompt and skill requirements.

## Quality Targets

This phase should produce measurable improvements without claiming arbitrary perfect reconstruction.

Target outcomes:

- Maple pages 4, 6, and 7 no longer fail editability or raster checks.
- At least one Maple manual-review page improves visual score after a region-directed repair.
- Validator reports include non-null `region` values for visual fidelity issues when diff evidence supports a region.
- Runner repair reports list selected action names, changed element ids, and source validator issue references.
- Sample evaluation reports include generated-vs-ideal PPTX structure deltas.
- Full worker and web test suites remain green.

## Task 1: Extend Validator Issues With Region Evidence And Action Hints

**Files:**
- Modify: `apps/worker/src/autofacodex/contracts.py`
- Modify: `apps/worker/tests/test_contracts.py`

- [x] **Step 1: Write failing contract test**

Append this test to `apps/worker/tests/test_contracts.py`:

```python
def test_validator_issue_accepts_region_evidence_and_action_hints():
    report = ValidatorReport(
        task_id="task_region",
        attempt=2,
        aggregate_status="manual_review",
        pages=[
            {
                "page_number": 4,
                "status": "manual_review",
                "visual_score": 0.87,
                "editable_score": 1.0,
                "text_coverage_score": 1.0,
                "raster_fallback_ratio": 0.0,
                "issues": [
                    {
                        "type": "visual_fidelity",
                        "message": "Largest diff region is shifted relative to source",
                        "suggested_action": "adjust_bbox",
                        "region": [0.12, 0.18, 0.42, 0.33],
                        "evidence_paths": [
                            "output/diagnostics-v2/page-004-diff.png",
                            "output/diagnostics-v2/page-004-compare.png",
                        ],
                        "repair_hints": {
                            "action": "adjust_bbox",
                            "target_element_types": ["image", "shape", "text"],
                            "max_delta_inches": 0.15,
                        },
                    }
                ],
            }
        ],
    )

    issue = report.pages[0].issues[0]
    assert issue.region == [0.12, 0.18, 0.42, 0.33]
    assert issue.repair_hints["action"] == "adjust_bbox"
```

- [x] **Step 2: Run the failing contract test**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_contracts.py::test_validator_issue_accepts_region_evidence_and_action_hints -q
```

Expected: FAIL because `repair_hints` is not part of the contract.

- [x] **Step 3: Add `repair_hints` to `ValidatorIssue`**

In `apps/worker/src/autofacodex/contracts.py`, update `ValidatorIssue`:

```python
class ValidatorIssue(ContractModel):
    type: str
    message: str
    suggested_action: str
    region: IssueRegion | None = None
    evidence_paths: list[str] = Field(default_factory=list)
    repair_hints: dict = Field(default_factory=dict)
```

- [x] **Step 4: Run contract tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_contracts.py -q
```

Expected: PASS.

## Task 2: Extract Visual Diff Regions

**Files:**
- Modify: `apps/worker/src/autofacodex/tools/visual_diff.py`
- Create: `apps/worker/tests/test_visual_diff_regions.py`

- [x] **Step 1: Write failing tests for region extraction**

Create `apps/worker/tests/test_visual_diff_regions.py`:

```python
from pathlib import Path

from PIL import Image, ImageDraw

from autofacodex.tools.visual_diff import extract_diff_regions


def test_extract_diff_regions_returns_normalized_bounding_boxes(tmp_path: Path):
    source = tmp_path / "source.png"
    candidate = tmp_path / "candidate.png"
    Image.new("RGB", (100, 100), "white").save(source)
    changed = Image.new("RGB", (100, 100), "white")
    draw = ImageDraw.Draw(changed)
    draw.rectangle([20, 30, 49, 59], fill="black")
    changed.save(candidate)

    regions = extract_diff_regions(source, candidate, threshold=0.1, min_area_ratio=0.01)

    assert regions == [
        {
            "region": [0.2, 0.3, 0.5, 0.6],
            "area_ratio": 0.09,
        }
    ]


def test_extract_diff_regions_filters_tiny_noise(tmp_path: Path):
    source = tmp_path / "source.png"
    candidate = tmp_path / "candidate.png"
    Image.new("RGB", (100, 100), "white").save(source)
    changed = Image.new("RGB", (100, 100), "white")
    changed.putpixel((1, 1), (0, 0, 0))
    changed.save(candidate)

    assert extract_diff_regions(source, candidate, threshold=0.1, min_area_ratio=0.01) == []
```

- [x] **Step 2: Run failing tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_visual_diff_regions.py -q
```

Expected: FAIL because `extract_diff_regions` does not exist.

- [x] **Step 3: Implement `extract_diff_regions`**

Add this function to `apps/worker/src/autofacodex/tools/visual_diff.py`:

```python
from PIL import Image, ImageChops


def extract_diff_regions(
    source_path: Path,
    candidate_path: Path,
    *,
    threshold: float = 0.1,
    min_area_ratio: float = 0.01,
    max_regions: int = 5,
) -> list[dict]:
    source = Image.open(source_path).convert("RGB")
    candidate = Image.open(candidate_path).convert("RGB")
    if source.size != candidate.size:
        candidate = candidate.resize(source.size)

    diff = ImageChops.difference(source, candidate).convert("L")
    width, height = diff.size
    pixels = diff.load()
    cutoff = int(max(0.0, min(1.0, threshold)) * 255)
    visited: set[tuple[int, int]] = set()
    regions: list[dict] = []

    for y in range(height):
        for x in range(width):
            if (x, y) in visited or pixels[x, y] <= cutoff:
                continue
            stack = [(x, y)]
            visited.add((x, y))
            xs: list[int] = []
            ys: list[int] = []
            while stack:
                cx, cy = stack.pop()
                xs.append(cx)
                ys.append(cy)
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    if (nx, ny) in visited or pixels[nx, ny] <= cutoff:
                        continue
                    visited.add((nx, ny))
                    stack.append((nx, ny))

            area_ratio = len(xs) / float(width * height)
            if area_ratio < min_area_ratio:
                continue
            min_x, max_x = min(xs), max(xs) + 1
            min_y, max_y = min(ys), max(ys) + 1
            regions.append(
                {
                    "region": [
                        round(min_x / width, 4),
                        round(min_y / height, 4),
                        round(max_x / width, 4),
                        round(max_y / height, 4),
                    ],
                    "area_ratio": round(area_ratio, 6),
                }
            )

    return sorted(regions, key=lambda item: item["area_ratio"], reverse=True)[:max_regions]
```

- [x] **Step 4: Run region tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_visual_diff_regions.py -q
```

Expected: PASS.

## Task 3: Add Region Evidence To Validator Reports

**Files:**
- Modify: `apps/worker/src/autofacodex/tools/validate_candidate.py`
- Modify: `apps/worker/tests/test_validate_candidate.py`

- [x] **Step 1: Write failing validator test**

Append this test to `apps/worker/tests/test_validate_candidate.py`:

```python
def test_validate_candidate_adds_visual_diff_region_and_repair_hint(tmp_path: Path, monkeypatch):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_task(task_dir, ppt_text="Editable Title")
    _stub_validation_tools(task_dir, monkeypatch)

    monkeypatch.setattr("autofacodex.tools.validate_candidate.compare_images", lambda *_args: 0.86)
    monkeypatch.setattr(
        "autofacodex.tools.validate_candidate.extract_diff_regions",
        lambda *_args, **_kwargs: [{"region": [0.2, 0.3, 0.5, 0.6], "area_ratio": 0.09}],
    )

    report = validate_candidate(task_dir, attempt=1)

    visual_issue = next(issue for issue in report.pages[0].issues if issue.type == "visual_fidelity")
    assert visual_issue.region == [0.2, 0.3, 0.5, 0.6]
    assert visual_issue.repair_hints["action"] == "adjust_bbox"
    assert visual_issue.repair_hints["diff_area_ratio"] == 0.09
```

- [x] **Step 2: Run the failing validator test**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_validate_candidate.py::test_validate_candidate_adds_visual_diff_region_and_repair_hint -q
```

Expected: FAIL because Validator does not yet call `extract_diff_regions`.

- [x] **Step 3: Import and use `extract_diff_regions`**

In `apps/worker/src/autofacodex/tools/validate_candidate.py`, import:

```python
from autofacodex.tools.visual_diff import compare_images, extract_diff_regions, write_compare_image, write_diff_image
```

Then compute visual regions after `visual_score`:

```python
visual_regions = extract_diff_regions(pdf_render, ppt_render)
largest_visual_region = visual_regions[0] if visual_regions else None
```

Update visual fidelity issue construction so the first region is attached:

```python
region = largest_visual_region["region"] if largest_visual_region else None
repair_hints = {
    "action": "adjust_bbox",
    "target_element_types": ["image", "shape", "text", "path"],
    "diff_area_ratio": largest_visual_region["area_ratio"] if largest_visual_region else 0,
}
```

- [x] **Step 4: Run validator tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_validate_candidate.py -q
```

Expected: PASS.

## Task 4: Implement Constrained Repair Actions

**Files:**
- Create: `apps/worker/src/autofacodex/tools/repair_actions.py`
- Create: `apps/worker/tests/test_repair_actions.py`

- [x] **Step 1: Write failing repair action tests**

Create `apps/worker/tests/test_repair_actions.py`:

```python
from autofacodex.tools.repair_actions import apply_repair_action


def _model():
    return {
        "slides": [
            {
                "page_number": 1,
                "size": {"width": 10, "height": 7.5},
                "elements": [
                    {
                        "id": "image-1",
                        "type": "image",
                        "x": 2.0,
                        "y": 2.0,
                        "w": 2.0,
                        "h": 1.0,
                        "style": {},
                    },
                    {
                        "id": "title",
                        "type": "text",
                        "x": 1.0,
                        "y": 1.0,
                        "w": 3.0,
                        "h": 0.5,
                        "text": "Title",
                        "style": {},
                    },
                ],
                "raster_fallback_regions": [],
            }
        ]
    }


def test_apply_repair_action_marks_region_images_as_background():
    model = _model()
    result = apply_repair_action(
        model,
        page_number=1,
        action={
            "action": "mark_region_background",
            "region": [0.1, 0.1, 0.5, 0.5],
            "min_overlap_ratio": 0.2,
        },
    )

    assert result["changed_element_ids"] == ["image-1"]
    image = model["slides"][0]["elements"][0]
    assert image["style"]["role"] == "background"


def test_apply_repair_action_noops_unknown_action():
    model = _model()
    result = apply_repair_action(
        model,
        page_number=1,
        action={"action": "unsupported_action", "region": [0, 0, 1, 1]},
    )

    assert result["changed_element_ids"] == []
    assert result["status"] == "noop"
```

- [x] **Step 2: Run failing tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_repair_actions.py -q
```

Expected: FAIL because `repair_actions.py` does not exist.

- [x] **Step 3: Implement `apply_repair_action`**

Create `apps/worker/src/autofacodex/tools/repair_actions.py`:

```python
from typing import Any


def _slide_for_page(model: dict[str, Any], page_number: int) -> dict[str, Any] | None:
    for slide in model.get("slides", []):
        if slide.get("page_number") == page_number:
            return slide
    return None


def _normalized_bbox(element: dict[str, Any], slide: dict[str, Any]) -> tuple[float, float, float, float]:
    size = slide.get("size") or {}
    width = float(size.get("width") or 1)
    height = float(size.get("height") or 1)
    x1 = float(element.get("x") or 0) / width
    y1 = float(element.get("y") or 0) / height
    x2 = (float(element.get("x") or 0) + float(element.get("w") or 0)) / width
    y2 = (float(element.get("y") or 0) + float(element.get("h") or 0)) / height
    return x1, y1, x2, y2


def _overlap_ratio(a: list[float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    b_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return 0.0 if b_area <= 0 else intersection / b_area


def apply_repair_action(
    model: dict[str, Any],
    *,
    page_number: int,
    action: dict[str, Any],
) -> dict[str, Any]:
    slide = _slide_for_page(model, page_number)
    if slide is None:
        return {"status": "noop", "changed_element_ids": [], "reason": "page_not_found"}

    action_name = action.get("action")
    if action_name != "mark_region_background":
        return {"status": "noop", "changed_element_ids": [], "reason": "unsupported_action"}

    region = action.get("region") or [0, 0, 0, 0]
    min_overlap_ratio = float(action.get("min_overlap_ratio", 0.2))
    changed: list[str] = []
    for element in slide.get("elements", []):
        if element.get("type") != "image":
            continue
        if _overlap_ratio(region, _normalized_bbox(element, slide)) < min_overlap_ratio:
            continue
        style = dict(element.get("style") or {})
        style["role"] = "background"
        element["style"] = style
        changed.append(str(element.get("id")))

    return {
        "status": "changed" if changed else "noop",
        "changed_element_ids": changed,
        "action": action_name,
    }
```

- [x] **Step 4: Run repair action tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_repair_actions.py -q
```

Expected: PASS.

## Task 5: Route Runner Through Validator Region Hints

**Files:**
- Modify: `apps/worker/src/autofacodex/tools/runner_repair.py`
- Modify: `apps/worker/tests/test_runner_repair.py`

- [x] **Step 1: Write failing Runner test**

Append this test to `apps/worker/tests/test_runner_repair.py`:

```python
def test_deterministic_runner_repair_uses_validator_region_hints(tmp_path: Path, monkeypatch):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    _write_repair_task(task_dir)
    report = ValidatorReport.model_validate_json(
        (task_dir / "reports" / "validator.v1.json").read_text(encoding="utf-8")
    )
    data = report.model_dump()
    data["pages"][0]["issues"].append(
        {
            "type": "visual_fidelity",
            "message": "Localized visual mismatch",
            "suggested_action": "adjust_bbox",
            "region": [0.0, 0.0, 1.0, 1.0],
            "repair_hints": {
                "action": "mark_region_background",
                "region": [0.0, 0.0, 1.0, 1.0],
                "min_overlap_ratio": 0.2,
            },
        }
    )
    (task_dir / "reports" / "validator.v1.json").write_text(
        ValidatorReport.model_validate(data).model_dump_json(indent=2),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "autofacodex.tools.runner_repair.generate_pptx",
        lambda _model, output_path, *, asset_root=None: output_path.write_bytes(b"pptx") or output_path,
    )

    result = run_deterministic_runner_repair(
        task_dir,
        source_attempt=1,
        target_attempt=2,
        reason="region_hint",
    )

    assert any(action["type"] == "validator_repair_hint" for action in result["actions"])
```

- [x] **Step 2: Run failing Runner test**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_runner_repair.py::test_deterministic_runner_repair_uses_validator_region_hints -q
```

Expected: FAIL because Runner does not consume repair hints.

- [x] **Step 3: Apply repair hints before background fallback**

In `apps/worker/src/autofacodex/tools/runner_repair.py`, import:

```python
from autofacodex.tools.repair_actions import apply_repair_action
```

Before `_repair_large_background_images`, iterate page issues:

```python
for issue in page.issues:
    if not issue.repair_hints:
        continue
    result = apply_repair_action(
        model_data,
        page_number=page.page_number,
        action=issue.repair_hints,
    )
    if result["changed_element_ids"]:
        actions.append(
            {
                "type": "validator_repair_hint",
                "page_number": page.page_number,
                "issue_type": issue.type,
                "repair_action": issue.repair_hints.get("action"),
                "changed_element_ids": result["changed_element_ids"],
            }
        )
```

- [x] **Step 4: Run Runner tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_runner_repair.py -q
```

Expected: PASS.

## Task 6: Compare Generated PPTX Against Ideal PPTX Structure

**Files:**
- Create: `apps/worker/src/autofacodex/evaluation/compare_ideal_pptx.py`
- Create: `apps/worker/tests/test_compare_ideal_pptx.py`
- Modify: `apps/worker/src/autofacodex/evaluation/run_samples.py`
- Modify: `apps/worker/tests/test_sample_discovery.py`

- [x] **Step 1: Write failing ideal comparison tests**

Create `apps/worker/tests/test_compare_ideal_pptx.py`:

```python
from pathlib import Path

from pptx import Presentation

from autofacodex.evaluation.compare_ideal_pptx import compare_pptx_structure


def _pptx(path: Path, texts: list[str]) -> None:
    prs = Presentation()
    blank = prs.slide_layouts[6]
    for text in texts:
        slide = prs.slides.add_slide(blank)
        box = slide.shapes.add_textbox(914400, 914400, 3657600, 914400)
        box.text = text
    prs.save(path)


def test_compare_pptx_structure_reports_page_count_and_text_delta(tmp_path: Path):
    generated = tmp_path / "generated.pptx"
    ideal = tmp_path / "ideal.pptx"
    _pptx(generated, ["One"])
    _pptx(ideal, ["One", "Two"])

    result = compare_pptx_structure(generated, ideal)

    assert result["generated_slide_count"] == 1
    assert result["ideal_slide_count"] == 2
    assert result["slide_count_delta"] == -1
    assert result["pages"][0]["generated_text_runs"] == 1
    assert result["pages"][0]["ideal_text_runs"] == 1
```

- [x] **Step 2: Run failing ideal comparison test**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_compare_ideal_pptx.py -q
```

Expected: FAIL because the module does not exist.

- [x] **Step 3: Implement `compare_pptx_structure`**

Create `apps/worker/src/autofacodex/evaluation/compare_ideal_pptx.py`:

```python
from pathlib import Path

from pptx import Presentation


def _slide_counts(slide) -> dict[str, int]:
    text_runs = 0
    pictures = 0
    shapes = 0
    tables = 0
    for shape in slide.shapes:
        if getattr(shape, "has_text_frame", False) and shape.text_frame.text.strip():
            text_runs += 1
        if shape.shape_type == 13:
            pictures += 1
        if getattr(shape, "has_table", False):
            tables += 1
        shapes += 1
    return {
        "text_runs": text_runs,
        "pictures": pictures,
        "shapes": shapes,
        "tables": tables,
    }


def compare_pptx_structure(generated_path: Path, ideal_path: Path) -> dict:
    generated = Presentation(generated_path)
    ideal = Presentation(ideal_path)
    page_count = max(len(generated.slides), len(ideal.slides))
    pages: list[dict] = []
    for index in range(page_count):
        generated_counts = (
            _slide_counts(generated.slides[index])
            if index < len(generated.slides)
            else {"text_runs": 0, "pictures": 0, "shapes": 0, "tables": 0}
        )
        ideal_counts = (
            _slide_counts(ideal.slides[index])
            if index < len(ideal.slides)
            else {"text_runs": 0, "pictures": 0, "shapes": 0, "tables": 0}
        )
        pages.append(
            {
                "page_number": index + 1,
                "generated_text_runs": generated_counts["text_runs"],
                "ideal_text_runs": ideal_counts["text_runs"],
                "generated_pictures": generated_counts["pictures"],
                "ideal_pictures": ideal_counts["pictures"],
                "generated_shapes": generated_counts["shapes"],
                "ideal_shapes": ideal_counts["shapes"],
                "generated_tables": generated_counts["tables"],
                "ideal_tables": ideal_counts["tables"],
            }
        )
    return {
        "generated_slide_count": len(generated.slides),
        "ideal_slide_count": len(ideal.slides),
        "slide_count_delta": len(generated.slides) - len(ideal.slides),
        "pages": pages,
    }
```

- [x] **Step 4: Add ideal comparison to sample reports**

In `apps/worker/src/autofacodex/evaluation/run_samples.py`, locate the per-sample summary writer. Add optional lookup of matching ideal PPTX by stem under `pdf-to-ppt/example-output`. When present, write:

```python
"ideal_comparison": compare_pptx_structure(final_pptx_path, ideal_pptx_path)
```

When absent, write:

```python
"ideal_comparison": None
```

- [x] **Step 5: Run evaluation tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_compare_ideal_pptx.py tests/test_sample_discovery.py -q
```

Expected: PASS.

## Task 7: Update Agent Prompts For Constrained Repair

**Files:**
- Modify: `apps/worker/agent_assets/runner/runner.system.md`
- Modify: `apps/worker/agent_assets/runner/SKILL.md`
- Modify: `apps/worker/agent_assets/validator/validator.system.md`
- Modify: `apps/worker/agent_assets/validator/SKILL.md`
- Modify: `apps/worker/tests/test_agent_assets.py`

- [x] **Step 1: Write failing prompt test**

Append this test to `apps/worker/tests/test_agent_assets.py`:

```python
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
```

- [x] **Step 2: Run failing prompt test**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_agent_assets.py::test_pdf_to_ppt_agents_require_region_hints_and_constrained_repair_actions -q
```

Expected: FAIL until the prompt assets mention these requirements.

- [x] **Step 3: Update Runner prompt and skill**

Add these requirements to `apps/worker/agent_assets/runner/runner.system.md` and `apps/worker/agent_assets/runner/SKILL.md`:

```text
- Prefer constrained repair actions from Validator `repair_hints` before free-form slide-model edits.
- Use only supported repair actions unless the task explicitly asks for a new action implementation.
- Record each constrained repair action in `reports/runner-repair.vN.json` with action name, page number, issue type, changed element ids, and remaining risk.
```

- [x] **Step 4: Update Validator prompt and skill**

Add these requirements to `apps/worker/agent_assets/validator/validator.system.md` and `apps/worker/agent_assets/validator/SKILL.md`:

```text
- Include region evidence for visual-fidelity issues whenever diff regions are available.
- Include `repair_hints` for Runner when an issue maps to a supported constrained repair action.
- Use `manual_review` when the page has remaining visual mismatch but no safe bounded repair hint.
```

- [x] **Step 5: Run prompt tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_agent_assets.py -q
```

Expected: PASS.

## Task 8: Run The Maple Regression Workflow

**Files:**
- No source file changes.
- Evidence output: new task directory under `shared-tasks/`.

- [x] **Step 1: Create a fresh Maple task**

Run from the repo root:

```bash
TASK="shared-tasks/next-phase-maple-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$TASK"
cp /home/alvin/AutoFaCodex/pdf-to-ppt/pdf-source/'Maple Pledge-高管访谈培训材料.pdf' "$TASK/input.pdf"
cat > "$TASK/task-manifest.json" <<EOF
{
  "task_id": "$(basename "$TASK")",
  "workflow_type": "pdf_to_ppt",
  "input_pdf": "input.pdf",
  "attempt": 1,
  "max_attempts": 2
}
EOF
```

- [x] **Step 2: Run the workflow**

Run:

```bash
TASK_DIR="$TASK" CODEX_AGENT_TIMEOUT_SECONDS=120 PYTHONPATH=apps/worker/src apps/worker/.venv/bin/python - <<'PY'
from pathlib import Path
from autofacodex.workflows.pdf_to_ppt import run_pdf_to_ppt
import os
run_pdf_to_ppt(Path(os.environ["TASK_DIR"]))
print(os.environ["TASK_DIR"])
PY
```

Expected: the task writes `output/candidate.v1.pptx`, `output/candidate.v2.pptx`, `reports/validator.v1.json`, `reports/validator.v2.json`, and logs for Runner and Validator.

- [x] **Step 3: Summarize validator deltas**

Run:

```bash
jq '{attempt, aggregate_status, pages:[.pages[]|{page:.page_number,status,visual:.visual_score,editable:.editable_score,text:.text_coverage_score,raster:.raster_fallback_ratio,issues:[.issues[].type]}]}' "$TASK/reports/validator.v1.json"
jq '{attempt, aggregate_status, pages:[.pages[]|{page:.page_number,status,visual:.visual_score,editable:.editable_score,text:.text_coverage_score,raster:.raster_fallback_ratio,issues:[.issues[].type]}]}' "$TASK/reports/validator.v2.json"
```

Expected: pages that remain below visual `0.90` include region evidence and repair hints, and at least one manual-review page improves its visual score or has a clear remaining reason.

## Task 9: Final Verification

**Files:**
- No source file changes unless prior tests reveal issues.

- [x] **Step 1: Run worker tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest -q
```

Expected: all worker tests pass.

- [x] **Step 2: Run web tests**

Run:

```bash
npm --workspace apps/web run test -- --run
```

Expected: all web tests pass.

- [x] **Step 3: Archive the next-phase evidence**

Create a short archive note at:

```text
docs/superpowers/archives/YYYY-MM-DD-pdf-to-ppt-visual-fidelity-next-phase-results.md
```

The archive note must include:

```text
Task directory:
Generated candidate paths:
Validator v1 summary:
Validator v2 summary:
Runner repair actions:
Remaining manual review pages:
Verification commands and results:
```

## Self-Review

Spec coverage:

- Region-level visual evidence is covered by Tasks 1 through 3.
- Constrained deterministic repair is covered by Tasks 4 and 5.
- Ideal PPTX comparison is covered by Task 6.
- Agent prompt alignment is covered by Task 7.
- Real Maple workflow verification is covered by Task 8.
- Full regression verification is covered by Task 9.

Unresolved marker scan:

- The plan contains no unresolved markers.
- Every task has exact files, commands, and expected results.

Type consistency:

- `repair_hints` is introduced on `ValidatorIssue`.
- `repair_hints["action"]` is consumed by `apply_repair_action`.
- Runner report action names are stable strings: `validator_repair_hint`, `mark_background_image`, and `mark_background_image_group`.
