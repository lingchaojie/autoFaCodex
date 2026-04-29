# PDF To PPT Regression Debug Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the regression-driven PDF to editable PPT quality loop: real rendering validation, editability inspection, text coverage, full-sample evaluation reports, and evidence-based Runner/Validator instructions.

**Architecture:** The Worker remains responsible for conversion and validation. Deterministic tools produce evidence first: PDF renders, PPTX renders, visual diffs, PPTX structure inspection, and text coverage. The workflow then writes strict Validator reports from those artifacts, and the sample evaluation harness aggregates every PDF in the sample set without PDF-specific conversion rules.

**Tech Stack:** Python 3.11, Pydantic, PyMuPDF, python-pptx, Pillow, scikit-image, LibreOffice, pytest, Next.js/Vitest for regression safety.

---

## File Map

- Modify `apps/worker/src/autofacodex/contracts.py`: add evidence fields to Validator contract while preserving existing required fields.
- Modify `contracts/validator-report.schema.json`: keep JSON schema in sync with the Python contract.
- Modify `apps/worker/tests/test_contracts.py`: prove Validator evidence fields validate and unknown fields remain rejected.
- Modify `apps/worker/src/autofacodex/tools/pptx_render.py`: make LibreOffice rendering robust and evidence-preserving.
- Create `apps/worker/tests/test_pptx_render.py`: test render command construction, profile paths, success, and failure diagnostics with mocks.
- Modify `apps/worker/src/autofacodex/tools/pptx_inspect.py`: expand PPTX XML inspection to include geometry, text content, largest image area ratio, and full-page image detection.
- Create `apps/worker/tests/test_pptx_inspect.py`: cover editable text extraction and full-page image detection.
- Create `apps/worker/src/autofacodex/tools/text_coverage.py`: compare source PDF text with editable PPTX text.
- Create `apps/worker/tests/test_text_coverage.py`: cover Chinese/English text normalization, missing text, and empty source handling.
- Modify `apps/worker/src/autofacodex/tools/visual_diff.py`: add diff and side-by-side diagnostic image writers.
- Create `apps/worker/src/autofacodex/tools/validate_candidate.py`: generate real Validator reports from evidence for one task attempt.
- Create `apps/worker/tests/test_validate_candidate.py`: cover pass, repair, full-page image rejection, and missing evidence.
- Modify `apps/worker/src/autofacodex/workflows/pdf_to_ppt.py`: replace initial fixed scores with `validate_candidate`.
- Modify `apps/worker/tests/test_pdf_to_ppt_workflow.py`: assert the workflow delegates to real validation and writes reports from it.
- Modify `apps/worker/src/autofacodex/evaluation/run_samples.py`: write aggregate sample reports.
- Modify `apps/worker/tests/test_sample_discovery.py`: cover aggregate report writing and CLI arguments.
- Modify `apps/worker/agent_assets/runner/runner.system.md`: require evidence-based slide model repair.
- Modify `apps/worker/agent_assets/runner/SKILL.md`: make the Runner repair sequence tool-driven.
- Modify `apps/worker/agent_assets/validator/validator.system.md`: require strict evidence paths and real page validation.
- Modify `apps/worker/agent_assets/validator/SKILL.md`: make Validator steps match the new tools.
- Modify `apps/worker/tests/test_agent_assets.py`: assert new prompt/skill requirements.

## Task 1: Extend Validator Contracts For Evidence

**Files:**
- Modify: `apps/worker/src/autofacodex/contracts.py`
- Modify: `contracts/validator-report.schema.json`
- Test: `apps/worker/tests/test_contracts.py`

- [ ] **Step 1: Write failing contract tests**

Append these tests to `apps/worker/tests/test_contracts.py`:

```python
def test_validator_report_accepts_page_and_issue_evidence_paths():
    report = ValidatorReport(
        task_id="task_123",
        attempt=1,
        pages=[
            {
                "page_number": 1,
                "status": "repair_needed",
                "visual_score": 0.75,
                "editable_score": 0.4,
                "text_coverage_score": 0.9,
                "raster_fallback_ratio": 0.6,
                "evidence_paths": {
                    "pdf_render": "renders/pdf/page-001.png",
                    "ppt_render": "output/rendered-pages-v1/page-001.png",
                    "diff": "output/diagnostics-v1/page-001-diff.png",
                    "inspection": "reports/inspection.v1.json",
                    "text_coverage": "reports/text-coverage.v1.json",
                },
                "issues": [
                    {
                        "type": "editability",
                        "message": "Large raster region detected",
                        "suggested_action": "Reconstruct visible text as editable text boxes",
                        "evidence_paths": ["reports/inspection.v1.json"],
                    }
                ],
            }
        ],
    )

    page = report.pages[0]
    assert page.evidence_paths["diff"] == "output/diagnostics-v1/page-001-diff.png"
    assert page.issues[0].evidence_paths == ["reports/inspection.v1.json"]


def test_validator_report_accepts_aggregate_status():
    report = ValidatorReport(
        task_id="task_123",
        attempt=1,
        aggregate_status="repair_needed",
        pages=[
            {
                "page_number": 1,
                "status": "repair_needed",
                "visual_score": 0.75,
                "editable_score": 0.4,
                "text_coverage_score": 0.9,
                "raster_fallback_ratio": 0.6,
                "issues": [],
            }
        ],
    )

    assert report.aggregate_status == "repair_needed"
```

- [ ] **Step 2: Run the failing contract tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_contracts.py -q
```

Expected: FAIL because `evidence_paths` and `aggregate_status` are currently forbidden extra fields.

- [ ] **Step 3: Update the Python contract**

In `apps/worker/src/autofacodex/contracts.py`, replace the Validator classes with this compatible version:

```python
class ValidatorIssue(ContractModel):
    type: str
    message: str
    suggested_action: str
    region: IssueRegion | None = None
    evidence_paths: list[str] = Field(default_factory=list)


class PageValidation(ContractModel):
    page_number: int = Field(ge=1)
    status: Literal["pass", "repair_needed", "manual_review", "failed"]
    visual_score: float = Field(ge=0, le=1)
    editable_score: float = Field(ge=0, le=1)
    text_coverage_score: float = Field(ge=0, le=1)
    raster_fallback_ratio: float = Field(ge=0, le=1)
    issues: list[ValidatorIssue] = Field(default_factory=list)
    evidence_paths: dict[str, str] = Field(default_factory=dict)


class ValidatorReport(ContractModel):
    task_id: str
    attempt: int = Field(ge=1)
    pages: list[PageValidation]
    aggregate_status: Literal["pass", "repair_needed", "manual_review", "failed"] | None = None
```

- [ ] **Step 4: Update the JSON schema**

Regenerate `contracts/validator-report.schema.json` from the updated Pydantic model:

```bash
cd apps/worker && PYTHONPATH=src .venv/bin/python - <<'PY'
import json
from pathlib import Path
from autofacodex.contracts import ValidatorReport

schema = ValidatorReport.model_json_schema()
Path("../../contracts/validator-report.schema.json").write_text(
    json.dumps(schema, indent=2),
    encoding="utf-8",
)
PY
```

- [ ] **Step 5: Run contract tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_contracts.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/worker/src/autofacodex/contracts.py contracts/validator-report.schema.json apps/worker/tests/test_contracts.py
git commit -m "feat: add validator evidence fields"
```

## Task 2: Make PPTX Rendering Robust And Evidence-Preserving

**Files:**
- Modify: `apps/worker/src/autofacodex/tools/pptx_render.py`
- Create: `apps/worker/tests/test_pptx_render.py`

- [ ] **Step 1: Write failing render tests**

Create `apps/worker/tests/test_pptx_render.py`:

```python
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from autofacodex.tools.pptx_render import render_pptx_pages, render_pptx_to_pdf


def test_render_pptx_to_pdf_uses_writable_profile_and_returns_pdf(tmp_path: Path):
    pptx = tmp_path / "candidate.v1.pptx"
    pptx.write_bytes(b"pptx")
    output_dir = tmp_path / "rendered-pdf"
    expected_pdf = output_dir / "candidate.v1.pdf"

    def fake_run(args, **kwargs):
        expected_pdf.parent.mkdir(parents=True)
        expected_pdf.write_bytes(b"%PDF-1.4")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="converted", stderr="")

    with patch("autofacodex.tools.pptx_render.subprocess.run", side_effect=fake_run) as run:
        result = render_pptx_to_pdf(pptx, output_dir, profile_root=tmp_path / "profiles")

    assert result == expected_pdf
    args = run.call_args.args[0]
    assert args[:3] == ["libreoffice", "--headless", "--convert-to"]
    assert any(str(arg).startswith("-env:UserInstallation=file://") for arg in args)
    assert run.call_args.kwargs["check"] is False
    assert run.call_args.kwargs["env"]["HOME"].startswith(str(tmp_path / "profiles"))


def test_render_pptx_to_pdf_reports_stdout_and_stderr_on_failure(tmp_path: Path):
    pptx = tmp_path / "candidate.v1.pptx"
    pptx.write_bytes(b"pptx")

    with patch(
        "autofacodex.tools.pptx_render.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["libreoffice"],
            returncode=7,
            stdout="stdout text",
            stderr="stderr text",
        ),
    ):
        with pytest.raises(RuntimeError, match="stdout text.*stderr text"):
            render_pptx_to_pdf(pptx, tmp_path / "rendered-pdf", profile_root=tmp_path / "profiles")


def test_render_pptx_pages_renders_pdf_pages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pptx = tmp_path / "candidate.v1.pptx"
    pptx.write_bytes(b"pptx")
    pdf = tmp_path / "candidate.v1.pdf"
    page = tmp_path / "page-001.png"

    monkeypatch.setattr("autofacodex.tools.pptx_render.render_pptx_to_pdf", lambda *_args, **_kwargs: pdf)
    monkeypatch.setattr("autofacodex.tools.pptx_render.render_pdf_pages", lambda *_args, **_kwargs: [page])

    result = render_pptx_pages(pptx, tmp_path / "ppt-render", profile_root=tmp_path / "profiles")

    assert result.output_pdf == pdf
    assert result.page_images == [page]
```

- [ ] **Step 2: Run render tests to verify failure**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pptx_render.py -q
```

Expected: FAIL because `render_pptx_pages` and `profile_root` support do not exist.

- [ ] **Step 3: Replace the render tool implementation**

Replace `apps/worker/src/autofacodex/tools/pptx_render.py` with:

```python
from dataclasses import dataclass
import os
import subprocess
from pathlib import Path

from autofacodex.tools.pdf_render import render_pdf_pages


@dataclass(frozen=True)
class PptxRenderResult:
    output_pdf: Path
    page_images: list[Path]


def _profile_dir(profile_root: Path | None, pptx_path: Path) -> Path:
    root = profile_root if profile_root is not None else pptx_path.parent / ".libreoffice"
    return root / f"profile-{pptx_path.stem}"


def render_pptx_to_pdf(
    pptx_path: Path,
    output_dir: Path,
    profile_root: Path | None = None,
    libreoffice_bin: str = "libreoffice",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = _profile_dir(profile_root, pptx_path)
    profile_dir.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "HOME": str(profile_dir / "home"),
        "XDG_RUNTIME_DIR": str(profile_dir / "runtime"),
    }
    Path(env["HOME"]).mkdir(parents=True, exist_ok=True)
    Path(env["XDG_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(env["XDG_RUNTIME_DIR"]).chmod(0o700)
    result = subprocess.run(
        [
            libreoffice_bin,
            "--headless",
            "--convert-to",
            "pdf",
            f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
            "--outdir",
            str(output_dir),
            str(pptx_path),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    output_pdf = output_dir / f"{pptx_path.stem}.pdf"
    if result.returncode != 0 or not output_pdf.is_file():
        raise RuntimeError(
            f"LibreOffice failed to render {pptx_path} to {output_pdf}. "
            f"returncode={result.returncode} stdout={result.stdout or ''} stderr={result.stderr or ''}"
        )
    return output_pdf


def render_pptx_pages(
    pptx_path: Path,
    output_dir: Path,
    zoom: float = 2.0,
    profile_root: Path | None = None,
    libreoffice_bin: str = "libreoffice",
) -> PptxRenderResult:
    rendered_pdf_dir = output_dir / "rendered-pdf"
    rendered_pages_dir = output_dir / "rendered-pages"
    output_pdf = render_pptx_to_pdf(
        pptx_path,
        rendered_pdf_dir,
        profile_root=profile_root,
        libreoffice_bin=libreoffice_bin,
    )
    page_images = render_pdf_pages(output_pdf, rendered_pages_dir, zoom=zoom)
    return PptxRenderResult(output_pdf=output_pdf, page_images=page_images)
```

- [ ] **Step 4: Run render tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pptx_render.py -q
```

Expected: PASS.

- [ ] **Step 5: Run existing Worker tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/worker/src/autofacodex/tools/pptx_render.py apps/worker/tests/test_pptx_render.py
git commit -m "feat: harden pptx rendering"
```

## Task 3: Expand PPTX Editability Inspection

**Files:**
- Modify: `apps/worker/src/autofacodex/tools/pptx_inspect.py`
- Create: `apps/worker/tests/test_pptx_inspect.py`

- [ ] **Step 1: Write failing inspection tests**

Create `apps/worker/tests/test_pptx_inspect.py`:

```python
from pathlib import Path

from PIL import Image

from autofacodex.contracts import SlideModel
from autofacodex.tools.pptx_generate import generate_pptx
from autofacodex.tools.pptx_inspect import inspect_pptx_editability


def _model(slide: dict) -> SlideModel:
    return SlideModel(slides=[slide])


def test_inspect_pptx_returns_editable_text_content(tmp_path: Path):
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
                }
            ],
            "raster_fallback_regions": [],
        }
    )
    output = tmp_path / "candidate.pptx"
    generate_pptx(model, output)

    inspection = inspect_pptx_editability(output)

    page = inspection["pages"][0]
    assert page["text"] == "Editable Title"
    assert page["text_runs"] == 1
    assert page["pictures"] == 0
    assert page["largest_picture_area_ratio"] == 0
    assert page["has_full_page_picture"] is False


def test_inspect_pptx_detects_full_page_picture(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (1200, 675), color=(240, 240, 240)).save(image_path)
    model = _model(
        {
            "page_number": 1,
            "size": {"width": 13.333, "height": 7.5},
            "elements": [
                {
                    "id": "page-image",
                    "type": "image",
                    "source": str(image_path),
                    "x": 0,
                    "y": 0,
                    "w": 13.333,
                    "h": 7.5,
                }
            ],
            "raster_fallback_regions": [],
        }
    )
    output = tmp_path / "candidate.pptx"
    generate_pptx(model, output)

    inspection = inspect_pptx_editability(output)

    page = inspection["pages"][0]
    assert page["pictures"] == 1
    assert page["largest_picture_area_ratio"] > 0.98
    assert page["has_full_page_picture"] is True
```

- [ ] **Step 2: Run inspection tests to verify failure**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pptx_inspect.py -q
```

Expected: FAIL because the current inspector does not return text content or image area ratios.

- [ ] **Step 3: Replace inspection implementation**

Replace `apps/worker/src/autofacodex/tools/pptx_inspect.py` with an implementation that keeps existing count keys and adds geometry:

```python
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


SLIDE_XML_RE = re.compile(r"^ppt/slides/slide\d+\.xml$")
NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
EMU_PER_INCH = 914400


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _slide_number(slide_name: str) -> int:
    return int(slide_name.removeprefix("ppt/slides/slide").removesuffix(".xml"))


def _emu(value: str | None) -> float:
    return float(value or 0) / EMU_PER_INCH


def _presentation_size(archive: ZipFile) -> tuple[float, float]:
    root = ET.fromstring(archive.read("ppt/presentation.xml"))
    size = root.find(".//p:sldSz", NS)
    if size is None:
        return (10.0, 7.5)
    return (_emu(size.attrib.get("cx")), _emu(size.attrib.get("cy")))


def _geometry(node: ET.Element) -> dict[str, float]:
    off = node.find(".//a:xfrm/a:off", NS)
    ext = node.find(".//a:xfrm/a:ext", NS)
    return {
        "x": _emu(off.attrib.get("x") if off is not None else None),
        "y": _emu(off.attrib.get("y") if off is not None else None),
        "w": _emu(ext.attrib.get("cx") if ext is not None else None),
        "h": _emu(ext.attrib.get("cy") if ext is not None else None),
    }


def _area_ratio(geometry: dict[str, float], slide_width: float, slide_height: float) -> float:
    slide_area = slide_width * slide_height
    if slide_area <= 0:
        return 0.0
    return max(0.0, geometry["w"] * geometry["h"] / slide_area)


def inspect_pptx_editability(pptx_path: Path) -> dict:
    with ZipFile(pptx_path) as archive:
        slide_width, slide_height = _presentation_size(archive)
        slide_names = sorted(
            (name for name in archive.namelist() if SLIDE_XML_RE.fullmatch(name)),
            key=_slide_number,
        )
        pages = []
        for slide_name in slide_names:
            root = ET.fromstring(archive.read(slide_name))
            nodes = list(root.iter())
            pictures = [_geometry(node) for node in root.findall(".//p:pic", NS)]
            shapes = [_geometry(node) for node in root.findall(".//p:sp", NS)]
            text_runs = [node.text or "" for node in root.findall(".//a:t", NS)]
            picture_area_ratios = [
                _area_ratio(geometry, slide_width, slide_height) for geometry in pictures
            ]
            largest_picture_area_ratio = max(picture_area_ratios, default=0.0)
            pages.append(
                {
                    "slide": slide_name,
                    "size": {"width": slide_width, "height": slide_height},
                    "text_runs": sum(1 for node in nodes if _localname(node.tag) == "t"),
                    "pictures": sum(1 for node in nodes if _localname(node.tag) == "pic"),
                    "shapes": sum(1 for node in nodes if _localname(node.tag) == "sp"),
                    "tables": sum(1 for node in nodes if _localname(node.tag) == "tbl"),
                    "text": "".join(text_runs),
                    "picture_geometries": pictures,
                    "shape_geometries": shapes,
                    "largest_picture_area_ratio": largest_picture_area_ratio,
                    "has_full_page_picture": largest_picture_area_ratio >= 0.92,
                }
            )
    return {"pages": pages}
```

- [ ] **Step 4: Run inspection tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pptx_inspect.py -q
```

Expected: PASS.

- [ ] **Step 5: Run PPTX generation tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pptx_generation.py tests/test_pptx_inspect.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/worker/src/autofacodex/tools/pptx_inspect.py apps/worker/tests/test_pptx_inspect.py
git commit -m "feat: inspect pptx editability details"
```

## Task 4: Add Text Coverage Scoring

**Files:**
- Create: `apps/worker/src/autofacodex/tools/text_coverage.py`
- Create: `apps/worker/tests/test_text_coverage.py`

- [ ] **Step 1: Write failing text coverage tests**

Create `apps/worker/tests/test_text_coverage.py`:

```python
from autofacodex.tools.text_coverage import compare_text_coverage, normalize_text


def test_normalize_text_handles_whitespace_and_full_width_punctuation():
    assert normalize_text("高管 访谈\nTraining，Materials") == "高管访谈training,materials"


def test_compare_text_coverage_scores_complete_text_as_one():
    result = compare_text_coverage("高管访谈培训材料", "高管 访谈 培训 材料")

    assert result["score"] == 1.0
    assert result["missing_ratio"] == 0.0


def test_compare_text_coverage_detects_missing_source_text():
    result = compare_text_coverage("Executive Interview Training Materials", "Executive Training")

    assert 0 < result["score"] < 1
    assert result["missing_ratio"] > 0
    assert "interview" in result["missing_text"].lower()


def test_compare_text_coverage_accepts_empty_source_text():
    result = compare_text_coverage("", "")

    assert result["score"] == 1.0
    assert result["source_length"] == 0
```

- [ ] **Step 2: Run text coverage tests to verify failure**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_text_coverage.py -q
```

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement text coverage**

Create `apps/worker/src/autofacodex/tools/text_coverage.py`:

```python
from collections import Counter
import re
import unicodedata


PUNCT_TRANSLATION = str.maketrans(
    {
        "，": ",",
        "。": ".",
        "：": ":",
        "；": ";",
        "（": "(",
        "）": ")",
        "！": "!",
        "？": "?",
    }
)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = normalized.translate(PUNCT_TRANSLATION).lower()
    return re.sub(r"\s+", "", normalized)


def _missing_text(source: str, candidate_counter: Counter[str]) -> str:
    remaining = candidate_counter.copy()
    missing: list[str] = []
    for char in source:
        if remaining[char] > 0:
            remaining[char] -= 1
        else:
            missing.append(char)
    return "".join(missing)


def compare_text_coverage(source_text: str, candidate_text: str) -> dict:
    source = normalize_text(source_text)
    candidate = normalize_text(candidate_text)
    if not source:
        return {
            "score": 1.0,
            "missing_ratio": 0.0,
            "missing_text": "",
            "source_length": 0,
            "candidate_length": len(candidate),
        }
    if source in candidate:
        return {
            "score": 1.0,
            "missing_ratio": 0.0,
            "missing_text": "",
            "source_length": len(source),
            "candidate_length": len(candidate),
        }
    missing = _missing_text(source, Counter(candidate))
    missing_ratio = len(missing) / len(source)
    score = max(0.0, min(1.0, 1.0 - missing_ratio))
    return {
        "score": score,
        "missing_ratio": missing_ratio,
        "missing_text": missing,
        "source_length": len(source),
        "candidate_length": len(candidate),
    }
```

- [ ] **Step 4: Run text coverage tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_text_coverage.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/worker/src/autofacodex/tools/text_coverage.py apps/worker/tests/test_text_coverage.py
git commit -m "feat: score editable text coverage"
```

## Task 5: Add Visual Diagnostic Images

**Files:**
- Modify: `apps/worker/src/autofacodex/tools/visual_diff.py`
- Create: `apps/worker/tests/test_visual_diff.py`

- [ ] **Step 1: Write failing diagnostic tests**

Create `apps/worker/tests/test_visual_diff.py`:

```python
from pathlib import Path

from PIL import Image

from autofacodex.tools.visual_diff import compare_images, write_compare_image, write_diff_image


def test_write_diff_image_creates_png(tmp_path: Path):
    reference = tmp_path / "reference.png"
    candidate = tmp_path / "candidate.png"
    output = tmp_path / "diff.png"
    Image.new("RGB", (10, 10), color=(255, 255, 255)).save(reference)
    Image.new("RGB", (10, 10), color=(0, 0, 0)).save(candidate)

    result = write_diff_image(reference, candidate, output)

    assert result == output
    assert output.is_file()
    assert Image.open(output).size == (10, 10)


def test_write_compare_image_places_images_side_by_side(tmp_path: Path):
    reference = tmp_path / "reference.png"
    candidate = tmp_path / "candidate.png"
    output = tmp_path / "compare.png"
    Image.new("RGB", (10, 10), color=(255, 255, 255)).save(reference)
    Image.new("RGB", (10, 10), color=(0, 0, 0)).save(candidate)

    result = write_compare_image(reference, candidate, output)

    assert result == output
    assert Image.open(output).size == (20, 10)


def test_compare_images_still_scores_identical_images(tmp_path: Path):
    reference = tmp_path / "reference.png"
    candidate = tmp_path / "candidate.png"
    Image.new("RGB", (10, 10), color=(255, 255, 255)).save(reference)
    Image.new("RGB", (10, 10), color=(255, 255, 255)).save(candidate)

    assert compare_images(reference, candidate) == 1.0
```

- [ ] **Step 2: Run diagnostic tests to verify failure**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_visual_diff.py -q
```

Expected: FAIL because diagnostic writers do not exist.

- [ ] **Step 3: Add diagnostic writers**

First adjust the import line at the top of `apps/worker/src/autofacodex/tools/visual_diff.py`:

```python
from PIL import Image, ImageChops
```

Then append these functions to `apps/worker/src/autofacodex/tools/visual_diff.py`:

```python

def write_diff_image(reference: Path, candidate: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(reference) as ref_image, Image.open(candidate) as cand_image:
        ref = ref_image.convert("RGB")
        cand = cand_image.convert("RGB").resize(ref.size)
        diff = ImageChops.difference(ref, cand)
        diff.save(output_path)
    return output_path


def write_compare_image(reference: Path, candidate: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(reference) as ref_image, Image.open(candidate) as cand_image:
        ref = ref_image.convert("RGB")
        cand = cand_image.convert("RGB").resize(ref.size)
        combined = Image.new("RGB", (ref.width + cand.width, ref.height), color=(255, 255, 255))
        combined.paste(ref, (0, 0))
        combined.paste(cand, (ref.width, 0))
        combined.save(output_path)
    return output_path
```

- [ ] **Step 4: Run visual diff tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_visual_diff.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/worker/src/autofacodex/tools/visual_diff.py apps/worker/tests/test_visual_diff.py
git commit -m "feat: write visual diagnostics"
```

## Task 6: Generate Real Validator Reports

**Files:**
- Create: `apps/worker/src/autofacodex/tools/validate_candidate.py`
- Modify: `apps/worker/src/autofacodex/agents/validator_runtime.py`
- Create: `apps/worker/tests/test_validate_candidate.py`

- [ ] **Step 1: Write failing Validator tests**

Create `apps/worker/tests/test_validate_candidate.py`:

```python
import json
from pathlib import Path

from PIL import Image

from autofacodex.contracts import SlideModel, ValidatorReport
from autofacodex.tools.validate_candidate import validate_candidate


def _write_task(task_dir: Path, *, ppt_text: str, full_page_picture: bool = False) -> None:
    (task_dir / "renders" / "pdf").mkdir(parents=True)
    (task_dir / "output").mkdir(parents=True)
    (task_dir / "slides").mkdir(parents=True)
    (task_dir / "extracted").mkdir(parents=True)
    Image.new("RGB", (20, 20), color=(255, 255, 255)).save(task_dir / "renders" / "pdf" / "page-001.png")
    (task_dir / "output" / "candidate.v1.pptx").write_bytes(b"pptx")
    (task_dir / "extracted" / "pages.json").write_text(
        json.dumps({"pages": [{"page_number": 1, "width": 20, "height": 20, "text": "Editable Title"}]}),
        encoding="utf-8",
    )
    model = SlideModel(
        slides=[
            {
                "page_number": 1,
                "size": {"width": 10, "height": 7.5},
                "elements": [],
                "raster_fallback_regions": [],
            }
        ]
    )
    (task_dir / "slides" / "slide-model.v1.json").write_text(model.model_dump_json(indent=2), encoding="utf-8")
    inspection = {
        "pages": [
            {
                "slide": "ppt/slides/slide1.xml",
                "text_runs": 1 if ppt_text else 0,
                "pictures": 1 if full_page_picture else 0,
                "shapes": 1,
                "tables": 0,
                "text": ppt_text,
                "largest_picture_area_ratio": 0.99 if full_page_picture else 0,
                "has_full_page_picture": full_page_picture,
            }
        ]
    }
    (task_dir / "reports").mkdir(parents=True)
    (task_dir / "reports" / "inspection.v1.json").write_text(json.dumps(inspection), encoding="utf-8")


def test_validate_candidate_passes_high_quality_editable_page(tmp_path: Path, monkeypatch):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_task(task_dir, ppt_text="Editable Title")
    rendered_page = task_dir / "output" / "rendered-pages-v1" / "page-001.png"

    monkeypatch.setattr(
        "autofacodex.tools.validate_candidate.render_pptx_pages",
        lambda *_args, **_kwargs: type("RenderResult", (), {"page_images": [rendered_page], "output_pdf": task_dir / "output" / "rendered-pdf-v1" / "candidate.v1.pdf"})(),
    )
    monkeypatch.setattr("autofacodex.tools.validate_candidate.compare_images", lambda *_args: 0.96)
    monkeypatch.setattr("autofacodex.tools.validate_candidate.write_diff_image", lambda *_args: _args[2])
    monkeypatch.setattr("autofacodex.tools.validate_candidate.write_compare_image", lambda *_args: _args[2])
    monkeypatch.setattr(
        "autofacodex.tools.validate_candidate.inspect_pptx_editability",
        lambda *_args: json.loads((task_dir / "reports" / "inspection.v1.json").read_text(encoding="utf-8")),
    )

    report = validate_candidate(task_dir, attempt=1)

    assert report.aggregate_status == "pass"
    assert report.pages[0].status == "pass"
    assert report.pages[0].visual_score == 0.96
    assert report.pages[0].text_coverage_score == 1.0
    assert (task_dir / "reports" / "validator.v1.json").is_file()
    ValidatorReport.model_validate_json((task_dir / "reports" / "validator.v1.json").read_text(encoding="utf-8"))


def test_validate_candidate_rejects_full_page_picture(tmp_path: Path, monkeypatch):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    _write_task(task_dir, ppt_text="Editable Title", full_page_picture=True)
    rendered_page = task_dir / "output" / "rendered-pages-v1" / "page-001.png"

    monkeypatch.setattr(
        "autofacodex.tools.validate_candidate.render_pptx_pages",
        lambda *_args, **_kwargs: type("RenderResult", (), {"page_images": [rendered_page], "output_pdf": task_dir / "output" / "rendered-pdf-v1" / "candidate.v1.pdf"})(),
    )
    monkeypatch.setattr("autofacodex.tools.validate_candidate.compare_images", lambda *_args: 0.96)
    monkeypatch.setattr("autofacodex.tools.validate_candidate.write_diff_image", lambda *_args: _args[2])
    monkeypatch.setattr("autofacodex.tools.validate_candidate.write_compare_image", lambda *_args: _args[2])
    monkeypatch.setattr(
        "autofacodex.tools.validate_candidate.inspect_pptx_editability",
        lambda *_args: json.loads((task_dir / "reports" / "inspection.v1.json").read_text(encoding="utf-8")),
    )

    report = validate_candidate(task_dir, attempt=1)

    assert report.aggregate_status == "repair_needed"
    assert report.pages[0].status == "repair_needed"
    assert any(issue.type == "editability" for issue in report.pages[0].issues)
```

- [ ] **Step 2: Run Validator tests to verify failure**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_validate_candidate.py -q
```

Expected: FAIL because `validate_candidate` does not exist.

- [ ] **Step 3: Implement real validation**

Create `apps/worker/src/autofacodex/tools/validate_candidate.py`:

```python
import json
from pathlib import Path

from autofacodex.contracts import PageValidation, SlideModel, ValidatorIssue, ValidatorReport
from autofacodex.tools.pptx_inspect import inspect_pptx_editability
from autofacodex.tools.pptx_render import render_pptx_pages
from autofacodex.tools.text_coverage import compare_text_coverage
from autofacodex.tools.visual_diff import compare_images, write_compare_image, write_diff_image


def _candidate_path(task_dir: Path, attempt: int) -> Path:
    return task_dir / "output" / f"candidate.v{attempt}.pptx"


def _slide_model_path(task_dir: Path, attempt: int) -> Path:
    return task_dir / "slides" / f"slide-model.v{attempt}.json"


def _raster_ratio(model: SlideModel, page_index: int) -> float:
    slide = model.slides[page_index]
    slide_area = slide.size.width * slide.size.height
    if slide_area <= 0:
        return 1.0
    fallback_area = sum(region.w * region.h for region in slide.raster_fallback_regions)
    return max(0.0, min(1.0, fallback_area / slide_area))


def _status_from_scores(
    visual_score: float,
    editable_score: float,
    text_score: float,
    raster_ratio: float,
    has_full_page_picture: bool,
) -> str:
    if has_full_page_picture or raster_ratio >= 0.5 or editable_score < 0.5:
        return "repair_needed"
    if visual_score < 0.85 or text_score < 0.8:
        return "repair_needed"
    if visual_score < 0.9:
        return "manual_review"
    return "pass"


def _issues(
    visual_score: float,
    editable_score: float,
    text_score: float,
    raster_ratio: float,
    has_full_page_picture: bool,
    evidence_paths: dict[str, str],
) -> list[ValidatorIssue]:
    issues: list[ValidatorIssue] = []
    if has_full_page_picture or raster_ratio >= 0.5 or editable_score < 0.5:
        issues.append(
            ValidatorIssue(
                type="editability",
                message="Slide uses excessive raster content or lacks editable structure",
                suggested_action="Reconstruct visible text, shapes, tables, and bounded image regions as editable PPT elements",
                evidence_paths=[evidence_paths["inspection"]],
            )
        )
    if visual_score < 0.9:
        issues.append(
            ValidatorIssue(
                type="visual_fidelity",
                message="Rendered PPTX differs from the source PDF page",
                suggested_action="Use the diff and compare images to adjust element positions, sizes, colors, z-order, and missing regions",
                evidence_paths=[evidence_paths["diff"], evidence_paths["compare"]],
            )
        )
    if text_score < 0.8:
        issues.append(
            ValidatorIssue(
                type="text_coverage",
                message="Editable PPTX text does not cover source PDF text",
                suggested_action="Recover missing source text as editable text boxes",
                evidence_paths=[evidence_paths["text_coverage"]],
            )
        )
    return issues


def _aggregate_status(pages: list[PageValidation]) -> str:
    statuses = {page.status for page in pages}
    if "failed" in statuses:
        return "failed"
    if "repair_needed" in statuses:
        return "repair_needed"
    if "manual_review" in statuses:
        return "manual_review"
    return "pass"


def validate_candidate(task_dir: Path, attempt: int = 1) -> ValidatorReport:
    candidate = _candidate_path(task_dir, attempt)
    model = SlideModel.model_validate_json(_slide_model_path(task_dir, attempt).read_text(encoding="utf-8"))
    extracted = json.loads((task_dir / "extracted" / "pages.json").read_text(encoding="utf-8"))
    pdf_renders = sorted((task_dir / "renders" / "pdf").glob("page-*.png"))
    render_result = render_pptx_pages(candidate, task_dir / "output" / f"ppt-render-v{attempt}")
    inspection = inspect_pptx_editability(candidate)
    reports_dir = task_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    inspection_path = reports_dir / f"inspection.v{attempt}.json"
    inspection_path.write_text(json.dumps(inspection, indent=2, ensure_ascii=False), encoding="utf-8")
    diagnostics_dir = task_dir / "output" / f"diagnostics-v{attempt}"
    text_coverage_rows = []
    pages: list[PageValidation] = []
    page_count = len(extracted["pages"])
    if len(pdf_renders) != page_count or len(render_result.page_images) != page_count:
        raise RuntimeError(
            f"Validation requires {page_count} PDF and PPT renders; "
            f"got {len(pdf_renders)} PDF renders and {len(render_result.page_images)} PPT renders"
        )
    for index in range(page_count):
        page_number = index + 1
        pdf_render = pdf_renders[index]
        ppt_render = render_result.page_images[index]
        diff_path = diagnostics_dir / f"page-{page_number:03d}-diff.png"
        compare_path = diagnostics_dir / f"page-{page_number:03d}-compare.png"
        write_diff_image(pdf_render, ppt_render, diff_path)
        write_compare_image(pdf_render, ppt_render, compare_path)
        visual_score = compare_images(pdf_render, ppt_render)
        page_inspection = inspection["pages"][index]
        text_coverage = compare_text_coverage(extracted["pages"][index].get("text", ""), page_inspection.get("text", ""))
        text_coverage_rows.append({"page_number": page_number, **text_coverage})
        raster_ratio = max(_raster_ratio(model, index), float(page_inspection.get("largest_picture_area_ratio", 0.0)) if page_inspection.get("has_full_page_picture") else 0.0)
        editable_score = 0.0 if page_inspection.get("has_full_page_picture") else min(1.0, (page_inspection.get("text_runs", 0) + page_inspection.get("shapes", 0)) / 1.0)
        text_score = float(text_coverage["score"])
        evidence_paths = {
            "pdf_render": str(pdf_render.relative_to(task_dir)),
            "ppt_render": str(ppt_render.relative_to(task_dir)),
            "diff": str(diff_path.relative_to(task_dir)),
            "compare": str(compare_path.relative_to(task_dir)),
            "inspection": str(inspection_path.relative_to(task_dir)),
            "text_coverage": f"reports/text-coverage.v{attempt}.json",
        }
        status = _status_from_scores(
            visual_score,
            editable_score,
            text_score,
            raster_ratio,
            bool(page_inspection.get("has_full_page_picture")),
        )
        pages.append(
            PageValidation(
                page_number=page_number,
                status=status,
                visual_score=visual_score,
                editable_score=editable_score,
                text_coverage_score=text_score,
                raster_fallback_ratio=raster_ratio,
                evidence_paths=evidence_paths,
                issues=_issues(
                    visual_score,
                    editable_score,
                    text_score,
                    raster_ratio,
                    bool(page_inspection.get("has_full_page_picture")),
                    evidence_paths,
                ),
            )
        )
    text_coverage_path = reports_dir / f"text-coverage.v{attempt}.json"
    text_coverage_path.write_text(json.dumps(text_coverage_rows, indent=2, ensure_ascii=False), encoding="utf-8")
    report = ValidatorReport(
        task_id=task_dir.name,
        attempt=attempt,
        pages=pages,
        aggregate_status=_aggregate_status(pages),
    )
    (reports_dir / f"validator.v{attempt}.json").write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return report
```

- [ ] **Step 4: Keep `build_validator_report` compatible**

In `apps/worker/src/autofacodex/agents/validator_runtime.py`, keep the existing `build_validator_report` function and update the final return to include aggregate status:

```python
    report = ValidatorReport(task_id=task_id, attempt=attempt, pages=pages)
    statuses = {page.status for page in pages}
    if "failed" in statuses:
        aggregate = "failed"
    elif "repair_needed" in statuses:
        aggregate = "repair_needed"
    elif "manual_review" in statuses:
        aggregate = "manual_review"
    else:
        aggregate = "pass"
    return report.model_copy(update={"aggregate_status": aggregate})
```

- [ ] **Step 5: Run Validator tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_validate_candidate.py tests/test_contracts.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/worker/src/autofacodex/tools/validate_candidate.py apps/worker/src/autofacodex/agents/validator_runtime.py apps/worker/tests/test_validate_candidate.py
git commit -m "feat: validate pptx candidates from evidence"
```

## Task 7: Integrate Real Validation Into Initial Workflow

**Files:**
- Modify: `apps/worker/src/autofacodex/workflows/pdf_to_ppt.py`
- Modify: `apps/worker/tests/test_pdf_to_ppt_workflow.py`

- [ ] **Step 1: Write failing workflow test**

Add this test to `apps/worker/tests/test_pdf_to_ppt_workflow.py`:

```python
def test_run_pdf_to_ppt_initial_uses_real_candidate_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    make_pdf(task_dir / "input.pdf")
    calls = []

    def fake_validate_candidate(received_task_dir: Path, attempt: int):
        calls.append((received_task_dir, attempt))
        report = ValidatorReport(
            task_id=received_task_dir.name,
            attempt=attempt,
            aggregate_status="repair_needed",
            pages=[
                {
                    "page_number": 1,
                    "status": "repair_needed",
                    "visual_score": 0.5,
                    "editable_score": 1.0,
                    "text_coverage_score": 1.0,
                    "raster_fallback_ratio": 0,
                    "issues": [],
                }
            ],
        )
        (received_task_dir / "reports").mkdir(parents=True, exist_ok=True)
        (received_task_dir / "reports" / "validator.v1.json").write_text(
            report.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return report

    monkeypatch.setattr(workflow, "validate_candidate", fake_validate_candidate)

    run_pdf_to_ppt(task_dir)

    assert calls == [(task_dir, 1)]
```

- [ ] **Step 2: Run workflow test to verify failure**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pdf_to_ppt_workflow.py::test_run_pdf_to_ppt_initial_uses_real_candidate_validation -q
```

Expected: FAIL because the workflow still builds fixed scores directly.

- [ ] **Step 3: Replace fixed initial report generation**

In `apps/worker/src/autofacodex/workflows/pdf_to_ppt.py`:

1. Add this import:

```python
from autofacodex.tools.validate_candidate import validate_candidate
```

2. Remove the `inspect_pptx_editability` and `build_validator_report` imports if no longer used by the initial path.

3. Replace the fixed report block at the end of `_run_initial`:

```python
    candidate = generate_pptx(slide_model, task_dir / "output" / "candidate.v1.pptx")
    validate_candidate(task_dir, attempt=1)
```

- [ ] **Step 4: Run workflow tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pdf_to_ppt_workflow.py -q
```

Expected: PASS.

- [ ] **Step 5: Run Worker tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest -q
```

Expected: PASS. If LibreOffice is unavailable in the test environment, no unit test should call the real binary because render behavior is mocked outside integration runs.

- [ ] **Step 6: Commit**

```bash
git add apps/worker/src/autofacodex/workflows/pdf_to_ppt.py apps/worker/tests/test_pdf_to_ppt_workflow.py
git commit -m "feat: use real validation in pdf to ppt workflow"
```

## Task 8: Aggregate Full-Sample Evaluation Reports

**Files:**
- Modify: `apps/worker/src/autofacodex/evaluation/run_samples.py`
- Modify: `apps/worker/tests/test_sample_discovery.py`

- [ ] **Step 1: Write failing evaluation summary test**

Append this test to `apps/worker/tests/test_sample_discovery.py`:

```python
def test_run_samples_writes_aggregate_report(tmp_path: Path, monkeypatch):
    samples_dir = tmp_path / "samples"
    output_root = tmp_path / "evaluation"
    samples_dir.mkdir()
    (samples_dir / "a.pdf").write_bytes(b"pdf a")

    def fake_run_pdf_to_ppt(task_dir: Path) -> None:
        reports = task_dir / "reports"
        reports.mkdir(parents=True)
        (reports / "validator.v1.json").write_text(
            """{
              "task_id": "sample-001-a",
              "attempt": 1,
              "aggregate_status": "repair_needed",
              "pages": [{
                "page_number": 1,
                "status": "repair_needed",
                "visual_score": 0.75,
                "editable_score": 1.0,
                "text_coverage_score": 1.0,
                "raster_fallback_ratio": 0.0,
                "issues": [{"type": "visual_fidelity", "message": "low score", "suggested_action": "adjust layout"}]
              }]
            }""",
            encoding="utf-8",
        )

    monkeypatch.setattr(samples, "run_pdf_to_ppt", fake_run_pdf_to_ppt)

    samples.run_samples(samples_dir, output_root)

    summary = output_root / "evaluation-summary.json"
    assert summary.is_file()
    text = summary.read_text(encoding="utf-8")
    assert '"sample_count": 1' in text
    assert '"average_visual_score": 0.75' in text
    assert '"visual_fidelity": 1' in text
```

- [ ] **Step 2: Run evaluation test to verify failure**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_sample_discovery.py::test_run_samples_writes_aggregate_report -q
```

Expected: FAIL because `run_samples` does not write an aggregate report.

- [ ] **Step 3: Add summary helpers**

In `apps/worker/src/autofacodex/evaluation/run_samples.py`, add imports:

```python
import json

from autofacodex.contracts import ValidatorReport
```

Add these functions above `run_samples`:

```python
def _latest_validator_report(task_dir: Path) -> ValidatorReport:
    reports = sorted((task_dir / "reports").glob("validator.v*.json"))
    if not reports:
        raise FileNotFoundError(f"No validator report found in {task_dir / 'reports'}")
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
    average_visual = sum(page.visual_score for page in pages) / len(pages) if pages else 0.0
    summary = {
        "sample_count": len(task_dirs),
        "page_count": len(pages),
        "average_visual_score": round(average_visual, 4),
        "min_visual_score": round(min((page.visual_score for page in pages), default=0.0), 4),
        "aggregate_status_counts": {
            status: sum(1 for report in reports if report.aggregate_status == status)
            for status in ["pass", "repair_needed", "manual_review", "failed"]
        },
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
                ) if report.pages else 0.0,
                "min_visual_score": round(min((page.visual_score for page in report.pages), default=0.0), 4),
            }
            for task_dir, report in zip(task_dirs, reports, strict=True)
        ],
    }
    path = output_root / "evaluation-summary.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
```

Update `run_samples` after the loop:

```python
    write_evaluation_summary(task_dirs, output_root)
    return task_dirs
```

Update `main` so callers can pass sample and output paths explicitly:

```python
def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run PDF to PPT conversion over sample PDFs.")
    parser.add_argument("samples_dir", nargs="?", type=Path, default=Path("pdf-to-ppt-test-samples"))
    parser.add_argument("output_root", nargs="?", type=Path, default=Path("shared-tasks/evaluation"))
    args = parser.parse_args()
    run_samples(args.samples_dir, args.output_root)
```

- [ ] **Step 4: Run sample discovery tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_sample_discovery.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/worker/src/autofacodex/evaluation/run_samples.py apps/worker/tests/test_sample_discovery.py
git commit -m "feat: summarize pdf to ppt sample evaluations"
```

## Task 9: Update Runner And Validator Agent Assets

**Files:**
- Modify: `apps/worker/agent_assets/runner/runner.system.md`
- Modify: `apps/worker/agent_assets/runner/SKILL.md`
- Modify: `apps/worker/agent_assets/validator/validator.system.md`
- Modify: `apps/worker/agent_assets/validator/SKILL.md`
- Modify: `apps/worker/tests/test_agent_assets.py`

- [ ] **Step 1: Write failing prompt asset assertions**

Append these assertions to existing tests in `apps/worker/tests/test_agent_assets.py`:

```python
def test_runner_prompt_requires_evidence_based_slide_model_repair():
    text = Path("agent_assets/runner/runner.system.md").read_text(encoding="utf-8")
    assert "reports/validator.vN.json" in text
    assert "slides/slide-model.vN.json" in text
    assert "runner-repair.vN.json" in text
    assert "Do not validate your own output" in text
    assert "bounded raster fallback" in text


def test_validator_prompt_requires_real_evidence_paths():
    text = Path("agent_assets/validator/validator.system.md").read_text(encoding="utf-8")
    assert "PDF render" in text
    assert "PPTX render" in text
    assert "visual diff" in text
    assert "text coverage" in text
    assert "full-page picture" in text
    assert "evidence_paths" in text
```

- [ ] **Step 2: Run agent asset tests to verify failure**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_agent_assets.py -q
```

Expected: FAIL because prompts do not yet contain the stricter evidence phrases.

- [ ] **Step 3: Update Runner system prompt**

Add this block to `apps/worker/agent_assets/runner/runner.system.md` after the Rules list:

```markdown
Evidence-based repair protocol:
- Read the latest `reports/validator.vN.json` before changing anything.
- Use the report's `evidence_paths`, page statuses, issue types, regions, and suggested actions as the repair scope.
- Modify `slides/slide-model.vN.json`; do not hand-edit generated PPTX internals.
- Regenerate the candidate with the provided deterministic PPTX generation command.
- Write `reports/runner-repair.vN.json` with changed pages, changed elements, evidence used, tools run, files written, bounded raster fallback decisions, and remaining risks.
- Do not validate your own output. The Validator owns rendering, diffing, scoring, and pass decisions.
- If a repair requires raster content, use bounded raster fallback only and record the region and reason.
```

- [ ] **Step 4: Update Runner skill**

Replace `apps/worker/agent_assets/runner/SKILL.md` body steps with:

```markdown
1. Read `task-manifest.json`.
2. Read the latest `reports/validator.vN.json`.
3. Identify pages with `repair_needed` or `manual_review`.
4. Read only the relevant `evidence_paths`, slide model pages, PDF extraction data, and user messages.
5. Update editable elements in `slides/slide-model.vN.json`.
6. Avoid full-page screenshots and record any bounded raster fallback region.
7. Regenerate the PPTX through the provided tool command.
8. Write `reports/runner-repair.vN.json` and a concise task event.
9. Stop after one bounded repair pass so the Validator can re-score from real evidence.
```

- [ ] **Step 5: Update Validator system prompt**

Add this block to `apps/worker/agent_assets/validator/validator.system.md` after the Rules list:

```markdown
Evidence requirements:
- Use PDF render paths, PPTX render paths, visual diff paths, PPTX inspection paths, and text coverage paths.
- Write those paths into `evidence_paths` for each page and issue.
- Reject a slide with a full-page picture or high raster fallback ratio even when visual score is high.
- Report visual, editability, and text coverage problems separately.
- Give Runner page-specific, region-specific repair instructions whenever evidence supports a region.
- If evidence is missing, mark the page `failed` or `manual_review`; do not pass it.
```

- [ ] **Step 6: Update Validator skill**

Replace `apps/worker/agent_assets/validator/SKILL.md` body steps with:

```markdown
1. Render source PDF pages or verify existing source renders.
2. Render candidate PPTX pages.
3. Compare every PDF/PPTX page pair visually.
4. Inspect PPTX internals for editable text, shapes, tables, images, largest picture ratio, and full-page picture usage.
5. Compare source PDF text against editable PPTX text.
6. Write diagnostic diff and compare image paths.
7. Reject full-page screenshots and excessive raster fallback.
8. Write strict `reports/validator.vN.json` with `evidence_paths`, scores, statuses, and repair instructions.
9. Recommend pass, repair, manual review, or failure from evidence only.
```

- [ ] **Step 7: Run asset tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_agent_assets.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/worker/agent_assets/runner/runner.system.md apps/worker/agent_assets/runner/SKILL.md apps/worker/agent_assets/validator/validator.system.md apps/worker/agent_assets/validator/SKILL.md apps/worker/tests/test_agent_assets.py
git commit -m "docs: tighten pdf to ppt agent instructions"
```

## Task 10: Run Full Verification And Baseline Sample Matrix

**Files:**
- No source edits unless a verification failure identifies a concrete defect.

- [ ] **Step 1: Run Worker tests**

Run:

```bash
cd apps/worker && .venv/bin/pytest -q
```

Expected: all Worker tests pass.

- [ ] **Step 2: Run Web tests**

Run:

```bash
npm --workspace apps/web run test -- --run
```

Expected: all Web tests pass.

- [ ] **Step 3: Run full sample evaluation**

Run from the worktree root, using the sample directory in the main repository:

```bash
PYTHONPATH=apps/worker/src apps/worker/.venv/bin/python -m autofacodex.evaluation.run_samples /home/alvin/AutoFaCodex/pdf-to-ppt-test-samples shared-tasks/evaluation
```

Expected: each sample PDF produces a task directory, `reports/validator.v1.json`, rendered candidate artifacts, diagnostics, and `shared-tasks/evaluation/evaluation-summary.json`.

- [ ] **Step 4: Inspect the aggregate report**

Run:

```bash
PYTHONPATH=apps/worker/src apps/worker/.venv/bin/python - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path("shared-tasks/evaluation/evaluation-summary.json").read_text(encoding="utf-8"))
print(json.dumps({
    "sample_count": summary["sample_count"],
    "page_count": summary["page_count"],
    "average_visual_score": summary["average_visual_score"],
    "min_visual_score": summary["min_visual_score"],
    "issue_counts": summary["issue_counts"],
}, ensure_ascii=False, indent=2))
PY
```

Expected: printed metrics show the current general baseline. The baseline does not have to meet the final 0.90 target in this task; it must be real evidence, not fixed scores.

- [ ] **Step 5: Check git status**

Run:

```bash
git status --short
```

Expected: only intentional source/test changes and generated sample artifacts appear. Do not commit `shared-tasks/` outputs unless the repository already tracks them for regression evidence.

- [ ] **Step 6: Commit final verification notes if docs changed**

If a brief verification note is added to a tracked doc, commit it:

```bash
git add docs/superpowers/plans/2026-04-27-pdf-to-ppt-regression-debug-implementation.md
git commit -m "docs: record pdf to ppt regression verification"
```

If no tracked docs changed, skip this commit.

## Self-Review Notes

- Spec coverage: the plan covers all sample PDFs, real rendering, visual diffs, editability inspection, text coverage, evidence paths, Runner/Validator prompt updates, and no PDF-specific conversion rules.
- Type consistency: `ValidatorIssue.evidence_paths`, `PageValidation.evidence_paths`, and `ValidatorReport.aggregate_status` are introduced in Task 1 and used by later tasks.
- Verification flow: unit tests are added before implementation in each task; full Worker, Web, and sample-matrix verification happen at the end.
- Scope control: commercial conversion providers and full-page screenshot acceptance are not introduced.
