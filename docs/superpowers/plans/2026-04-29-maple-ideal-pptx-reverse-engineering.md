# Maple Ideal PPTX Reverse Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Maple-first ideal PPTX profiling and comparison loop, then use its evidence to reduce generated PPTX object fragmentation without regressing editability or validation status.

**Architecture:** Extend PPTX inspection to expose text box geometry, add a focused strategy profiler under `autofacodex.evaluation`, enrich generated-vs-ideal comparison reports, and add a conservative slide-model builder heuristic that promotes dominant complex image regions while suppressing contained duplicate image/shape fragments. The acceptance gate is evidence-based: Maple structure deltas improve while validator status, editability, and text coverage do not regress.

**Tech Stack:** Python 3.11, pytest, python-pptx, XML parsing with `xml.etree.ElementTree`, existing `SlideModel` contracts, existing PDF-to-PPT workflow, jq-compatible JSON reports.

---

## File Map

- Modify `apps/worker/src/autofacodex/tools/pptx_inspect.py`: add text-box geometry evidence to existing PPTX XML inspection.
- Modify `apps/worker/tests/test_pptx_inspect.py`: cover text box count and geometries.
- Create `apps/worker/src/autofacodex/evaluation/pptx_strategy.py`: classify PPTX slide strategy and produce per-slide strategy profiles.
- Create `apps/worker/tests/test_pptx_strategy.py`: cover `background_plus_foreground_text`, `fragmented_objects`, `mostly_editable`, and `unknown`.
- Modify `apps/worker/src/autofacodex/evaluation/compare_ideal_pptx.py`: include generated/ideal strategy deltas in existing comparison output.
- Modify `apps/worker/tests/test_compare_ideal_pptx.py`: cover strategy fields and deltas.
- Modify `apps/worker/src/autofacodex/evaluation/run_samples.py`: write per-task `reports/ideal-comparison.json` when an ideal PPTX exists.
- Modify `apps/worker/tests/test_sample_discovery.py`: cover ideal comparison report writing.
- Modify `apps/worker/src/autofacodex/tools/slide_model_builder.py`: add dominant-background fragment suppression while preserving editable text.
- Modify `apps/worker/tests/test_pptx_generation.py`: cover background fragment suppression and no-op behavior.
- Create `docs/superpowers/archives/2026-04-29-maple-ideal-pptx-reverse-engineering-results.md`: archive Maple evidence after regression.

## Task 1: Add Text Box Geometry To PPTX Inspection

**Files:**
- Modify: `apps/worker/src/autofacodex/tools/pptx_inspect.py`
- Modify: `apps/worker/tests/test_pptx_inspect.py`

- [ ] **Step 1: Write the failing inspection test**

Append this test to `apps/worker/tests/test_pptx_inspect.py`:

```python
def test_inspect_pptx_reports_text_box_count_and_geometries(tmp_path: Path):
    model = _model(
        {
            "page_number": 1,
            "size": {"width": 10, "height": 7.5},
            "elements": [
                {
                    "id": "title",
                    "type": "text",
                    "text": "Editable Title",
                    "x": 1,
                    "y": 1,
                    "w": 4,
                    "h": 0.6,
                    "style": {"font_size": 24},
                },
                {
                    "id": "subtitle",
                    "type": "text",
                    "text": "Editable Subtitle",
                    "x": 2,
                    "y": 2,
                    "w": 3,
                    "h": 0.4,
                    "style": {"font_size": 14},
                },
            ],
            "raster_fallback_regions": [],
        }
    )
    output = tmp_path / "candidate.pptx"
    generate_pptx(model, output)

    inspection = inspect_pptx_editability(output)

    page = inspection["pages"][0]
    assert page["text_box_count"] == 2
    assert page["text_box_geometries"] == [
        {"x": pytest.approx(1), "y": pytest.approx(1), "w": pytest.approx(4), "h": pytest.approx(0.6)},
        {"x": pytest.approx(2), "y": pytest.approx(2), "w": pytest.approx(3), "h": pytest.approx(0.4)},
    ]
```

- [ ] **Step 2: Run the failing inspection test**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pptx_inspect.py::test_inspect_pptx_reports_text_box_count_and_geometries -q
```

Expected: FAIL with a missing `text_box_count` key.

- [ ] **Step 3: Implement text shape detection**

In `apps/worker/src/autofacodex/tools/pptx_inspect.py`, add this helper below `_geometry`:

```python
def _shape_text(node: ET.Element) -> str:
    return "".join(text_node.text or "" for text_node in node.findall(".//a:t", NS)).strip()
```

Then replace the shape-related block inside `inspect_pptx_editability` with this exact structure:

```python
            picture_nodes = root.findall(".//p:pic", NS)
            shape_nodes = root.findall(".//p:sp", NS)
            pictures = [_geometry(node) for node in picture_nodes]
            shapes = [_geometry(node) for node in shape_nodes]
            text_box_geometries = [
                _geometry(node) for node in shape_nodes if _shape_text(node)
            ]
            text_runs = [node.text or "" for node in root.findall(".//a:t", NS)]
```

Add these fields to the page dictionary returned by `inspect_pptx_editability`:

```python
                    "text_box_count": len(text_box_geometries),
                    "text_box_geometries": text_box_geometries,
```

- [ ] **Step 4: Run inspection tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pptx_inspect.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add apps/worker/src/autofacodex/tools/pptx_inspect.py apps/worker/tests/test_pptx_inspect.py
git commit -m "feat: expose pptx text box geometry"
```

## Task 2: Add PPTX Strategy Profiler

**Files:**
- Create: `apps/worker/src/autofacodex/evaluation/pptx_strategy.py`
- Create: `apps/worker/tests/test_pptx_strategy.py`

- [ ] **Step 1: Write failing profiler tests**

Create `apps/worker/tests/test_pptx_strategy.py`:

```python
from autofacodex.evaluation.pptx_strategy import (
    classify_slide_strategy,
    profile_pptx_strategy_from_inspection,
)


def test_classify_slide_strategy_background_plus_foreground_text():
    page = {
        "text_box_count": 3,
        "pictures": 3,
        "shapes": 8,
        "tables": 0,
        "largest_picture_area_ratio": 0.94,
        "total_picture_area_ratio": 1.0,
        "picture_coverage_ratio": 0.95,
        "picture_geometries": [{"x": 0, "y": 0, "w": 13.333, "h": 7.5}],
        "shape_geometries": [],
        "text_box_geometries": [{"x": 1, "y": 1, "w": 4, "h": 0.5}],
        "size": {"width": 13.333, "height": 7.5},
    }

    assert classify_slide_strategy(page) == "background_plus_foreground_text"


def test_classify_slide_strategy_fragmented_objects():
    page = {
        "text_box_count": 8,
        "pictures": 12,
        "shapes": 36,
        "tables": 0,
        "largest_picture_area_ratio": 0.72,
        "total_picture_area_ratio": 1.0,
        "picture_coverage_ratio": 0.89,
        "picture_geometries": [{"x": 0, "y": 1, "w": 9, "h": 5}],
        "shape_geometries": [],
        "text_box_geometries": [{"x": 1, "y": 1, "w": 4, "h": 0.5}],
        "size": {"width": 13.333, "height": 7.5},
    }

    assert classify_slide_strategy(page) == "fragmented_objects"


def test_classify_slide_strategy_mostly_editable():
    page = {
        "text_box_count": 6,
        "pictures": 1,
        "shapes": 4,
        "tables": 0,
        "largest_picture_area_ratio": 0.1,
        "total_picture_area_ratio": 0.1,
        "picture_coverage_ratio": 0.1,
        "picture_geometries": [{"x": 0, "y": 0, "w": 1, "h": 1}],
        "shape_geometries": [],
        "text_box_geometries": [{"x": 1, "y": 1, "w": 4, "h": 0.5}],
        "size": {"width": 13.333, "height": 7.5},
    }

    assert classify_slide_strategy(page) == "mostly_editable"


def test_profile_pptx_strategy_from_inspection_counts_strategies():
    inspection = {
        "pages": [
            {
                "slide": "ppt/slides/slide1.xml",
                "size": {"width": 13.333, "height": 7.5},
                "text_runs": 5,
                "text_box_count": 3,
                "pictures": 3,
                "shapes": 8,
                "tables": 0,
                "largest_picture_area_ratio": 0.94,
                "total_picture_area_ratio": 1.0,
                "picture_coverage_ratio": 0.95,
                "picture_geometries": [{"x": 0, "y": 0, "w": 13.333, "h": 7.5}],
                "shape_geometries": [],
                "text_box_geometries": [{"x": 1, "y": 1, "w": 4, "h": 0.5}],
            },
            {
                "slide": "ppt/slides/slide2.xml",
                "size": {"width": 13.333, "height": 7.5},
                "text_runs": 0,
                "text_box_count": 0,
                "pictures": 0,
                "shapes": 0,
                "tables": 0,
                "largest_picture_area_ratio": 0,
                "total_picture_area_ratio": 0,
                "picture_coverage_ratio": 0,
                "picture_geometries": [],
                "shape_geometries": [],
                "text_box_geometries": [],
            },
        ]
    }

    profile = profile_pptx_strategy_from_inspection(inspection)

    assert profile["strategy_counts"] == {
        "background_plus_foreground_text": 1,
        "fragmented_objects": 0,
        "mostly_editable": 0,
        "unknown": 1,
    }
    assert profile["pages"][0]["page_number"] == 1
    assert profile["pages"][0]["strategy"] == "background_plus_foreground_text"
```

- [ ] **Step 2: Run failing profiler tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pptx_strategy.py -q
```

Expected: FAIL because `autofacodex.evaluation.pptx_strategy` does not exist.

- [ ] **Step 3: Implement the profiler**

Create `apps/worker/src/autofacodex/evaluation/pptx_strategy.py`:

```python
from pathlib import Path
from typing import Any

from autofacodex.tools.pptx_inspect import inspect_pptx_editability


STRATEGIES = (
    "background_plus_foreground_text",
    "fragmented_objects",
    "mostly_editable",
    "unknown",
)


def _number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _count(page: dict[str, Any], field: str) -> int:
    try:
        return int(page.get(field, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _area_ratio(geometry: dict[str, Any], size: dict[str, Any]) -> float:
    width = _number(size.get("width"))
    height = _number(size.get("height"))
    if width <= 0 or height <= 0:
        return 0.0
    return max(
        0.0,
        min(1.0, _number(geometry.get("w")) * _number(geometry.get("h")) / (width * height)),
    )


def classify_slide_strategy(page: dict[str, Any]) -> str:
    text_boxes = _count(page, "text_box_count")
    pictures = _count(page, "pictures")
    shapes = _count(page, "shapes")
    coverage = _number(page.get("picture_coverage_ratio"))
    largest_picture = _number(page.get("largest_picture_area_ratio"))

    if not any((text_boxes, pictures, shapes, coverage, largest_picture)):
        return "unknown"
    if (pictures >= 10 or shapes >= 30) and largest_picture < 0.9:
        return "fragmented_objects"
    if coverage >= 0.82 and text_boxes >= 1:
        return "background_plus_foreground_text"
    if coverage <= 0.35 and text_boxes >= 2:
        return "mostly_editable"
    return "unknown"


def _dominant_background_candidates(page: dict[str, Any]) -> list[dict[str, Any]]:
    size = page.get("size") if isinstance(page.get("size"), dict) else {}
    candidates = []
    for geometry in page.get("picture_geometries", []):
        if not isinstance(geometry, dict):
            continue
        area_ratio = _area_ratio(geometry, size)
        if area_ratio >= 0.7:
            candidates.append({**geometry, "area_ratio": round(area_ratio, 6)})
    return sorted(candidates, key=lambda item: item["area_ratio"], reverse=True)


def profile_pptx_strategy_from_inspection(inspection: dict[str, Any]) -> dict[str, Any]:
    pages = []
    strategy_counts = {strategy: 0 for strategy in STRATEGIES}
    for index, page in enumerate(inspection.get("pages", []), start=1):
        strategy = classify_slide_strategy(page)
        strategy_counts[strategy] += 1
        pages.append(
            {
                "page_number": index,
                "slide": page.get("slide"),
                "size": page.get("size", {}),
                "strategy": strategy,
                "text_runs": _count(page, "text_runs"),
                "text_box_count": _count(page, "text_box_count"),
                "pictures": _count(page, "pictures"),
                "shapes": _count(page, "shapes"),
                "tables": _count(page, "tables"),
                "largest_picture_area_ratio": round(
                    _number(page.get("largest_picture_area_ratio")), 6
                ),
                "total_picture_area_ratio": round(
                    _number(page.get("total_picture_area_ratio")), 6
                ),
                "picture_coverage_ratio": round(
                    _number(page.get("picture_coverage_ratio")), 6
                ),
                "dominant_background_candidates": _dominant_background_candidates(page),
                "picture_geometries": page.get("picture_geometries", []),
                "shape_geometries": page.get("shape_geometries", []),
                "text_box_geometries": page.get("text_box_geometries", []),
            }
        )
    return {"pages": pages, "strategy_counts": strategy_counts}


def profile_pptx_strategy(pptx_path: Path) -> dict[str, Any]:
    return profile_pptx_strategy_from_inspection(inspect_pptx_editability(pptx_path))
```

- [ ] **Step 4: Run profiler tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pptx_strategy.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add apps/worker/src/autofacodex/evaluation/pptx_strategy.py apps/worker/tests/test_pptx_strategy.py
git commit -m "feat: profile pptx object strategy"
```

## Task 3: Enrich Ideal PPTX Comparison Reports

**Files:**
- Modify: `apps/worker/src/autofacodex/evaluation/compare_ideal_pptx.py`
- Modify: `apps/worker/tests/test_compare_ideal_pptx.py`
- Modify: `apps/worker/src/autofacodex/evaluation/run_samples.py`
- Modify: `apps/worker/tests/test_sample_discovery.py`

- [ ] **Step 1: Write failing comparison test**

Append this test to `apps/worker/tests/test_compare_ideal_pptx.py`:

```python
def test_compare_pptx_structure_includes_strategy_deltas(tmp_path: Path, monkeypatch):
    generated = tmp_path / "generated.pptx"
    ideal = tmp_path / "ideal.pptx"
    _pptx(generated, ["Generated"])
    _pptx(ideal, ["Ideal"])

    profiles = {
        generated: {
            "pages": [
                {
                    "page_number": 1,
                    "strategy": "fragmented_objects",
                    "text_box_count": 8,
                    "pictures": 12,
                    "shapes": 36,
                    "largest_picture_area_ratio": 0.72,
                    "picture_coverage_ratio": 0.89,
                }
            ]
        },
        ideal: {
            "pages": [
                {
                    "page_number": 1,
                    "strategy": "background_plus_foreground_text",
                    "text_box_count": 3,
                    "pictures": 3,
                    "shapes": 8,
                    "largest_picture_area_ratio": 0.94,
                    "picture_coverage_ratio": 0.95,
                }
            ]
        },
    }
    monkeypatch.setattr(
        "autofacodex.evaluation.compare_ideal_pptx.profile_pptx_strategy",
        lambda path: profiles[path],
    )

    result = compare_pptx_structure(generated, ideal)

    page = result["pages"][0]
    assert page["generated_strategy"] == "fragmented_objects"
    assert page["ideal_strategy"] == "background_plus_foreground_text"
    assert page["strategy_matches"] is False
    assert page["picture_count_delta"] == 9
    assert page["shape_count_delta"] == 28
    assert page["text_box_count_delta"] == 5
    assert page["largest_picture_area_ratio_delta"] == -0.22
    assert page["picture_coverage_ratio_delta"] == -0.06
```

- [ ] **Step 2: Write failing sample report test**

Append this test to `apps/worker/tests/test_sample_discovery.py`:

```python
def test_write_evaluation_summary_writes_per_task_ideal_comparison_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    output_root = tmp_path / "evaluation"
    task_dir = output_root / "sample-001-a"
    _write_validator_report(task_dir)
    final_pptx = task_dir / "output" / "final.pptx"
    final_pptx.parent.mkdir(parents=True)
    final_pptx.write_bytes(b"generated")
    ideal_pptx = tmp_path / "a.pptx"
    ideal_pptx.write_bytes(b"ideal")
    expected = {
        "generated_slide_count": 1,
        "ideal_slide_count": 1,
        "slide_count_delta": 0,
        "pages": [{"page_number": 1, "generated_strategy": "fragmented_objects"}],
    }

    monkeypatch.setattr(samples, "_ideal_pptx_path", lambda _task_dir: ideal_pptx, raising=False)
    monkeypatch.setattr(
        samples,
        "compare_pptx_structure",
        lambda generated_path, ideal_path: expected
        if generated_path == final_pptx and ideal_path == ideal_pptx
        else None,
        raising=False,
    )

    samples.write_evaluation_summary([task_dir], output_root)

    report_path = task_dir / "reports" / "ideal-comparison.json"
    assert json.loads(report_path.read_text(encoding="utf-8")) == expected
```

- [ ] **Step 3: Run failing comparison tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_compare_ideal_pptx.py::test_compare_pptx_structure_includes_strategy_deltas tests/test_sample_discovery.py::test_write_evaluation_summary_writes_per_task_ideal_comparison_report -q
```

Expected: FAIL because strategy deltas and per-task report writing are not implemented.

- [ ] **Step 4: Extend ideal comparison**

In `apps/worker/src/autofacodex/evaluation/compare_ideal_pptx.py`, add this import:

```python
from autofacodex.evaluation.pptx_strategy import profile_pptx_strategy
```

Add these helpers above `compare_pptx_structure`:

```python
def _profile_by_page(profile: dict) -> dict[int, dict]:
    return {
        int(page["page_number"]): page
        for page in profile.get("pages", [])
        if page.get("page_number") is not None
    }


def _profile_number(page: dict, field: str) -> float:
    try:
        return float(page.get(field, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _profile_int(page: dict, field: str) -> int:
    return int(_profile_number(page, field))


def _strategy_delta(generated_page: dict, ideal_page: dict) -> dict:
    return {
        "generated_strategy": generated_page.get("strategy", "unknown"),
        "ideal_strategy": ideal_page.get("strategy", "unknown"),
        "strategy_matches": generated_page.get("strategy") == ideal_page.get("strategy"),
        "picture_count_delta": _profile_int(generated_page, "pictures")
        - _profile_int(ideal_page, "pictures"),
        "shape_count_delta": _profile_int(generated_page, "shapes")
        - _profile_int(ideal_page, "shapes"),
        "text_box_count_delta": _profile_int(generated_page, "text_box_count")
        - _profile_int(ideal_page, "text_box_count"),
        "largest_picture_area_ratio_delta": round(
            _profile_number(generated_page, "largest_picture_area_ratio")
            - _profile_number(ideal_page, "largest_picture_area_ratio"),
            6,
        ),
        "picture_coverage_ratio_delta": round(
            _profile_number(generated_page, "picture_coverage_ratio")
            - _profile_number(ideal_page, "picture_coverage_ratio"),
            6,
        ),
    }
```

At the start of `compare_pptx_structure`, after opening both presentations, add:

```python
    generated_profiles = _profile_by_page(profile_pptx_strategy(generated_path))
    ideal_profiles = _profile_by_page(profile_pptx_strategy(ideal_path))
```

Inside the page loop, before appending the page dictionary, add:

```python
        generated_profile = generated_profiles.get(index + 1, {})
        ideal_profile = ideal_profiles.get(index + 1, {})
```

Then merge `_strategy_delta` into each page dictionary:

```python
                **_strategy_delta(generated_profile, ideal_profile),
```

- [ ] **Step 5: Write per-task ideal comparison reports**

In `apps/worker/src/autofacodex/evaluation/run_samples.py`, replace `_ideal_comparison` with this implementation:

```python
def _ideal_comparison(task_dir: Path) -> dict | None:
    final_pptx = task_dir / "output" / "final.pptx"
    ideal_pptx = _ideal_pptx_path(task_dir)
    if not final_pptx.is_file() or not ideal_pptx.is_file():
        return None
    comparison = compare_pptx_structure(final_pptx, ideal_pptx)
    reports_dir = task_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "ideal-comparison.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return comparison
```

- [ ] **Step 6: Run comparison and sample tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_compare_ideal_pptx.py tests/test_sample_discovery.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```bash
git add apps/worker/src/autofacodex/evaluation/compare_ideal_pptx.py apps/worker/tests/test_compare_ideal_pptx.py apps/worker/src/autofacodex/evaluation/run_samples.py apps/worker/tests/test_sample_discovery.py
git commit -m "feat: report ideal pptx strategy deltas"
```

## Task 4: Suppress Fragments Inside Dominant Background Regions

**Files:**
- Modify: `apps/worker/src/autofacodex/tools/slide_model_builder.py`
- Modify: `apps/worker/tests/test_pptx_generation.py`

- [ ] **Step 1: Write failing model-builder suppression test**

Append this test to `apps/worker/tests/test_pptx_generation.py`:

```python
def test_build_initial_slide_model_suppresses_fragments_inside_dominant_background_image():
    model = build_initial_slide_model(
        {
            "pages": [
                {
                    "page_number": 1,
                    "width": 960,
                    "height": 540,
                    "text": "Foreground Title",
                    "text_blocks": [
                        {
                            "type": "image",
                            "bbox": [0, 60, 960, 540],
                            "source": "objects/images/page-001-image-001.png",
                            "seqno": 1,
                        },
                        {
                            "type": "image",
                            "bbox": [320, 220, 460, 340],
                            "source": "objects/images/page-001-image-002.png",
                            "seqno": 2,
                        },
                        {
                            "type": "text",
                            "bbox": [72, 80, 360, 110],
                            "lines": [
                                {
                                    "bbox": [72, 80, 360, 110],
                                    "spans": [
                                        {
                                            "text": "Foreground Title",
                                            "bbox": [72, 80, 360, 110],
                                            "font": "Helvetica",
                                            "size": 24,
                                            "color": 0,
                                            "seqno": 4,
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "type": "image",
                            "bbox": [20, 20, 80, 80],
                            "source": "objects/images/page-001-image-003.png",
                            "seqno": 5,
                        },
                    ],
                    "drawings": [
                        {
                            "shape": "rect",
                            "bbox": [350, 260, 450, 300],
                            "fill": "#DDDDDD",
                            "stroke": "#DDDDDD",
                            "seqno": 3,
                        }
                    ],
                }
            ]
        }
    )

    elements = model.slides[0].elements
    assert [element.id for element in elements] == [
        "p1-image-1",
        "p1-text-1",
        "p1-image-3",
    ]
    assert elements[0].style["role"] == "background"
    assert elements[1].type == "text"
    assert elements[1].text == "Foreground Title"
    assert elements[2].source == "extracted/objects/images/page-001-image-003.png"
```

- [ ] **Step 2: Write no-op behavior test**

Append this test to `apps/worker/tests/test_pptx_generation.py`:

```python
def test_build_initial_slide_model_keeps_fragments_without_dominant_background_image():
    model = build_initial_slide_model(
        {
            "pages": [
                {
                    "page_number": 1,
                    "width": 960,
                    "height": 540,
                    "text": "",
                    "text_blocks": [
                        {
                            "type": "image",
                            "bbox": [0, 60, 400, 300],
                            "source": "objects/images/page-001-image-001.png",
                            "seqno": 1,
                        },
                        {
                            "type": "image",
                            "bbox": [320, 220, 460, 340],
                            "source": "objects/images/page-001-image-002.png",
                            "seqno": 2,
                        },
                    ],
                    "drawings": [],
                }
            ]
        }
    )

    assert [element.id for element in model.slides[0].elements] == [
        "p1-image-1",
        "p1-image-2",
    ]
    assert "role" not in model.slides[0].elements[0].style
```

- [ ] **Step 3: Run failing model-builder tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pptx_generation.py::test_build_initial_slide_model_suppresses_fragments_inside_dominant_background_image tests/test_pptx_generation.py::test_build_initial_slide_model_keeps_fragments_without_dominant_background_image -q
```

Expected: FAIL because the dominant image is not marked as background and contained fragments are not suppressed.

- [ ] **Step 4: Implement dominant background strategy helpers**

In `apps/worker/src/autofacodex/tools/slide_model_builder.py`, add these constants below `DECK_WIDTH`:

```python
DOMINANT_BACKGROUND_MIN_AREA_RATIO = 0.7
SUPPRESSED_FRAGMENT_MAX_AREA_RATIO = 0.2
SUPPRESSED_FRAGMENT_MIN_CONTAINMENT_RATIO = 0.95
```

Add these helpers below `_contains_bbox`:

```python
def _slide_area(size: SlideSize) -> float:
    return float(size.width) * float(size.height)


def _element_area_ratio_on_slide(element: SlideElement, size: SlideSize) -> float:
    area = _slide_area(size)
    if area <= 0:
        return 0.0
    return max(0.0, min(1.0, float(element.w) * float(element.h) / area))


def _containment_ratio(outer: list[float], inner: list[float]) -> float:
    if len(outer) != 4 or len(inner) != 4:
        return 0.0
    left = max(outer[0], inner[0])
    top = max(outer[1], inner[1])
    right = min(outer[2], inner[2])
    bottom = min(outer[3], inner[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    inner_area = max(0.0, inner[2] - inner[0]) * max(0.0, inner[3] - inner[1])
    if inner_area <= 0:
        return 0.0
    return intersection / inner_area


def _dominant_background_entry(
    positioned: list[tuple[int, int, SlideElement]],
    size: SlideSize,
) -> tuple[int, int, SlideElement] | None:
    candidates = [
        entry
        for entry in positioned
        if entry[2].type == "image"
        and _element_area_ratio_on_slide(entry[2], size) >= DOMINANT_BACKGROUND_MIN_AREA_RATIO
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda entry: _element_area_ratio_on_slide(entry[2], size))


def _should_suppress_background_fragment(
    element: SlideElement,
    dominant_background: SlideElement,
    size: SlideSize,
) -> bool:
    if element.id == dominant_background.id:
        return False
    if element.type in {"text", "table"}:
        return False
    if element.type not in {"image", "shape"}:
        return False
    if element.style.get("role") == "background":
        return False
    if _element_area_ratio_on_slide(element, size) > SUPPRESSED_FRAGMENT_MAX_AREA_RATIO:
        return False
    return (
        _containment_ratio(_element_bbox(dominant_background), _element_bbox(element))
        >= SUPPRESSED_FRAGMENT_MIN_CONTAINMENT_RATIO
    )


def _apply_dominant_background_strategy(
    positioned: list[tuple[int, int, SlideElement]],
    size: SlideSize,
) -> list[tuple[int, int, SlideElement]]:
    dominant_entry = _dominant_background_entry(positioned, size)
    if dominant_entry is None:
        return positioned

    dominant = dominant_entry[2]
    dominant.style = {**dominant.style, "role": "background"}
    return [
        entry
        for entry in positioned
        if not _should_suppress_background_fragment(entry[2], dominant, size)
    ]
```

Then update `_positioned_elements` so the final section is:

```python
    positioned = _collapse_table_regions(page["page_number"], positioned)
    positioned = _apply_dominant_background_strategy(positioned, size)
    positioned.sort(key=lambda item: (item[0], item[1]))
    return [element for _seq, _index, element in positioned]
```

- [ ] **Step 5: Run model-builder tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pptx_generation.py::test_build_initial_slide_model_suppresses_fragments_inside_dominant_background_image tests/test_pptx_generation.py::test_build_initial_slide_model_keeps_fragments_without_dominant_background_image -q
```

Expected: PASS.

- [ ] **Step 6: Run broader PPTX generation tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pptx_generation.py tests/test_validate_candidate.py tests/test_runner_repair.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

```bash
git add apps/worker/src/autofacodex/tools/slide_model_builder.py apps/worker/tests/test_pptx_generation.py
git commit -m "feat: suppress duplicated background fragments"
```

## Task 5: Run Maple Regression And Archive Evidence

**Files:**
- Create: `docs/superpowers/archives/2026-04-29-maple-ideal-pptx-reverse-engineering-results.md`

- [ ] **Step 1: Run targeted worker tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pptx_inspect.py tests/test_pptx_strategy.py tests/test_compare_ideal_pptx.py tests/test_sample_discovery.py tests/test_pptx_generation.py -q
```

Expected: PASS.

- [ ] **Step 2: Create a fresh Maple task directory**

Run from the repo root:

```bash
TASK="shared-tasks/maple-ideal-reverse-$(date +%Y%m%d-%H%M%S)"
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
echo "$TASK"
```

Expected: prints the new `shared-tasks/maple-ideal-reverse-*` directory.

- [ ] **Step 3: Run the Maple workflow**

Run:

```bash
TASK_DIR="$TASK" CODEX_AGENT_TIMEOUT_SECONDS=120 PYTHONPATH=apps/worker/src apps/worker/.venv/bin/python - <<'PY'
from pathlib import Path
import os

from autofacodex.workflows.pdf_to_ppt import run_pdf_to_ppt

task_dir = Path(os.environ["TASK_DIR"])
run_pdf_to_ppt(task_dir)
print(task_dir)
PY
```

Expected: exits `0` and writes `output/candidate.v1.pptx`, `output/candidate.v2.pptx`, `output/final.pptx`, `reports/validator.v1.json`, and `reports/validator.v2.json`.

- [ ] **Step 4: Write the Maple ideal comparison report**

Run:

```bash
TASK_DIR="$TASK" PYTHONPATH=apps/worker/src apps/worker/.venv/bin/python - <<'PY'
from pathlib import Path
import json
import os

from autofacodex.evaluation.compare_ideal_pptx import compare_pptx_structure

task_dir = Path(os.environ["TASK_DIR"])
ideal = Path("/home/alvin/AutoFaCodex/pdf-to-ppt/example-output/Maple Pledge-高管访谈培训材料.pptx")
comparison = compare_pptx_structure(task_dir / "output" / "final.pptx", ideal)
report_path = task_dir / "reports" / "ideal-comparison.json"
report_path.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(report_path)
PY
```

Expected: prints `$TASK/reports/ideal-comparison.json`.

- [ ] **Step 5: Summarize validator and ideal deltas**

Run:

```bash
jq '{attempt, aggregate_status, pages:[.pages[]|select(.page_number==4 or .page_number==6 or .page_number==7)|{page:.page_number,status,visual:.visual_score,editable:.editable_score,text:.text_coverage_score,raster:.raster_fallback_ratio,issues:[.issues[].type]}]}' "$TASK/reports/validator.v1.json"
jq '{attempt, aggregate_status, pages:[.pages[]|select(.page_number==4 or .page_number==6 or .page_number==7)|{page:.page_number,status,visual:.visual_score,editable:.editable_score,text:.text_coverage_score,raster:.raster_fallback_ratio,issues:[.issues[].type]}]}' "$TASK/reports/validator.v2.json"
jq '{pages:[.pages[]|select(.page_number==4 or .page_number==6 or .page_number==7)|{page:.page_number,generated_strategy,ideal_strategy,picture_count_delta,shape_count_delta,text_box_count_delta,largest_picture_area_ratio_delta,picture_coverage_ratio_delta}]}' "$TASK/reports/ideal-comparison.json"
```

Expected: pages 4, 6, and 7 remain at least `manual_review`, text coverage remains `1.0`, raster fallback does not return as a hard failure, and at least one page has a lower generated-vs-ideal object fragmentation delta than the previous Maple evidence.

- [ ] **Step 6: Run full worker tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest -q
```

Expected: PASS.

- [ ] **Step 7: Run web tests**

Run:

```bash
npm --workspace apps/web run test -- --run
```

Expected: PASS.

- [ ] **Step 8: Archive Maple evidence**

Create `docs/superpowers/archives/2026-04-29-maple-ideal-pptx-reverse-engineering-results.md` with this structure, using the exact task directory printed in Task 5 Step 2 and the exact summaries printed in Task 5 Step 5:

```markdown
# Maple Ideal PPTX Reverse Engineering Results

Date: 2026-04-29

## Task Directory

Use the exact `shared-tasks/maple-ideal-reverse-*` path printed in Task 5 Step 2.

## Generated Candidate Paths

- `output/candidate.v1.pptx`
- `output/candidate.v2.pptx`
- `output/final.pptx`

## Validator Summary

Include pages 4, 6, and 7 for validator v1 and v2 with status, visual score, editable score, text coverage score, raster fallback ratio, and issue types.

## Ideal Strategy Summary

Include pages 4, 6, and 7 from `reports/ideal-comparison.json` with generated strategy, ideal strategy, picture count delta, shape count delta, text box count delta, largest picture ratio delta, and picture coverage ratio delta.

## Acceptance Check

- Maple aggregate status did not regress below `manual_review`.
- Pages 4, 6, and 7 did not regress in text coverage.
- Generated-vs-ideal fragmentation improved on at least one of pages 4, 6, or 7.

## Verification Commands And Results

List the targeted worker test command, Maple workflow command, full worker test command, and web test command with pass/fail results.
```

- [ ] **Step 9: Commit Task 5**

```bash
git add docs/superpowers/archives/2026-04-29-maple-ideal-pptx-reverse-engineering-results.md
git commit -m "docs: archive maple ideal pptx evidence"
```

## Final Verification

- [ ] **Step 1: Check repository status**

Run:

```bash
git status --short
```

Expected: only pre-existing untracked `.codex` and `pdf-to-ppt/` remain, unless the implementation intentionally creates additional ignored task output under `shared-tasks/`.

- [ ] **Step 2: Verify latest commits**

Run:

```bash
git log --oneline -6
```

Expected: includes commits for inspection evidence, strategy profiling, ideal comparison deltas, fragment suppression, and Maple evidence archive.

## Self-Review

Spec coverage:

- Ideal strategy profiler is implemented by Tasks 1 and 2.
- Generated-vs-ideal explanatory comparison is implemented by Task 3.
- Model-builder adjustment is implemented by Task 4.
- Maple-only regression and archive evidence are implemented by Task 5.
- Validation and no-regression evidence are covered by Task 5 and Final Verification.

Placeholder scan:

- The plan contains no unresolved markers.
- Every task names exact files, tests, commands, and expected outcomes.

Type consistency:

- `text_box_count` and `text_box_geometries` are introduced by `inspect_pptx_editability`.
- `profile_pptx_strategy` consumes inspection dictionaries and returns page profiles.
- `compare_pptx_structure` consumes strategy profiles and emits stable delta keys.
- `run_samples` writes the same comparison object to `ideal_comparison` and `reports/ideal-comparison.json`.
- `slide_model_builder` keeps returning a valid `SlideModel`.
