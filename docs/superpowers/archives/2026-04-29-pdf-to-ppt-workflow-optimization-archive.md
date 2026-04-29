# PDF To PPT Workflow Optimization Archive

Date: 2026-04-29

## Scope

This archive records the PDF to editable PPT workflow investigation and optimization pass completed on 2026-04-29.

The work focused on the sample set under `/home/alvin/AutoFaCodex/pdf-to-ppt`, especially:

- Source PDF: `/home/alvin/AutoFaCodex/pdf-to-ppt/pdf-source/Maple Pledge-高管访谈培训材料.pdf`
- Ideal PPT reference: `/home/alvin/AutoFaCodex/pdf-to-ppt/example-output/Maple Pledge-高管访谈培训材料.pptx`
- Worktree: `/home/alvin/AutoFaCodex/.worktrees/pdf-to-ppt-mvp`

The goal was to understand why generated PPTX output differed from the example outputs, verify whether Runner and Validator agents were actually running, improve the workflow, and capture a complete v1 -> Validator -> repair -> v2 -> Validator log.

## Summary

The major finding is that high-quality example PPTX files are not fully vector-only. They use raster background content where appropriate, but keep foreground text and structure editable. The previous validator logic treated too much picture content as a failure even when the picture was a legitimate background layer. At the same time, the repair workflow depended too heavily on open-ended Codex subprocess agents, which could time out or exit without producing required artifacts.

This pass improved the workflow in three ways:

- Validator now allows declared PDF background images when editable foreground content remains present.
- Runner repair now has a deterministic fallback tool that can create required v2 artifacts when the agent times out or produces no artifacts.
- The repair workflow now records Agent timeout logs and continues with deterministic Runner and Validator fallback, producing a complete repair attempt instead of silently failing or hanging.

The workflow is better, but not perfect. The Maple sample moved from `repair_needed` to `manual_review` after the repair pass. Remaining failures are visual fidelity issues around layout, positioning, and complex page reconstruction rather than background/editability accounting.

## Files Changed In This Pass

Primary changes:

- `apps/worker/src/autofacodex/tools/runner_repair.py`
  - Added deterministic fallback repair for safe background-image promotion.
  - Writes `slides/slide-model.vN.json`, `output/candidate.vN.pptx`, and `reports/runner-repair.vN.json`.
  - Supports both single large background images and grouped image backgrounds.

- `apps/worker/src/autofacodex/workflows/pdf_to_ppt.py`
  - Added strict artifact checks for Runner and Validator repair attempts.
  - Added deterministic Runner fallback after Runner timeout or missing artifacts.
  - Added deterministic Validator fallback after Validator timeout, non-zero return, or missing report.
  - Added deterministic tool commands to Agent context.

- `apps/worker/src/autofacodex/tools/validate_candidate.py`
  - Stopped using total picture area as the only raster-fallback signal.
  - Uses largest picture ratio and picture coverage ratio.
  - Allows declared background images when foreground content is editable.
  - Downgrades low visual scores to `manual_review` when editability and text coverage are otherwise acceptable.

- `apps/worker/tests/test_runner_repair.py`
  - Added tests for single large background promotion and grouped background promotion.

- `apps/worker/tests/test_pdf_to_ppt_workflow.py`
  - Added coverage for deterministic fallback after Runner timeout, missing Runner artifacts, and missing Validator reports.

- `apps/worker/tests/test_validate_candidate.py`
  - Added coverage for declared PDF backgrounds and many bounded images.

Earlier related changes in the same worktree also updated:

- `apps/worker/src/autofacodex/tools/pptx_inspect.py`
  - Separates text runs with newlines instead of concatenating them directly, preventing false missing-text failures.

- `apps/worker/agent_assets/runner/runner.system.md`
- `apps/worker/agent_assets/runner/SKILL.md`
  - Clarifies background/foreground separation and required no-op artifact behavior.

## Root Cause Findings

### 1. The ideal PPTX strategy is hybrid, not fully vector

The Maple ideal output uses raster/image content for background-like regions, while keeping meaningful foreground text and structure editable. Treating every large image as a hard editability failure was too strict.

Correct target model:

```text
PDF page
  -> background image or color layer when it represents real visual background
  -> editable text, tables, labels, callouts, paths, and simple shapes above it
  -> bounded raster fallback only for regions that cannot be safely reconstructed
```

### 2. Validator picture accounting caused false failures

The previous validator behavior over-penalized image-heavy slides. In practice, many slides contain multiple legitimate image elements, and the total image area can exceed 50% even when the slide still has editable foreground content.

The revised logic distinguishes:

- full-slide screenshot with no declared background role: failure
- declared background image with editable foreground: allowed
- many bounded images without page-covering coverage: allowed
- high picture coverage with no background declaration: repair needed

### 3. Runner and Validator agents were running, but not reliably finishing

The agents did start through `codex exec`. The problem was that a return code or a long log did not guarantee required artifacts existed.

Observed before fallback:

- Runner Agent read files and validator reports.
- Runner Agent did not consistently write `slides/slide-model.v2.json`.
- Runner Agent did not consistently write `output/candidate.v2.pptx`.
- Runner Agent did not consistently write `reports/runner-repair.v2.json`.
- Validator Agent could also return without writing `reports/validator.v2.json`.

The workflow now treats missing artifacts as an explicit recoverable condition and falls back to deterministic repair or validation.

## Key Evidence

### Initial deterministic Maple baseline after validator fixes

Task directory:

```text
shared-tasks/investigation-maple-after-fixes-20260429-021633
```

Result:

- page 1 changed from false text coverage failure to pass.
- page 3 changed from editability/raster failure to pass.
- pages 4, 6, and 7 still needed repair due high raster accounting and visual fidelity.

### Complete workflow run with fallback

Task directory:

```text
shared-tasks/investigation-maple-grouped-fallback-20260429-023950
```

Important artifacts:

```text
output/candidate.v1.pptx
output/candidate.v2.pptx
output/final.pptx
slides/slide-model.v1.json
slides/slide-model.v2.json
slides/slide-model.final.v2.json
reports/validator.v1.json
reports/validator.v2.json
reports/runner-repair.v2.json
logs/runner-repair.log
logs/validator-repair.log
```

Runner log:

```text
shared-tasks/investigation-maple-grouped-fallback-20260429-023950/logs/runner-repair.log
```

Runner log facts:

- The Runner Agent was launched with the full Runner system prompt.
- The task prompt required `slides/slide-model.v2.json`, `output/candidate.v2.pptx`, and `reports/runner-repair.v2.json`.
- The Agent timed out after 45 seconds in the test run.
- The workflow appended a `deterministic runner fallback` section to the log.

Validator log:

```text
shared-tasks/investigation-maple-grouped-fallback-20260429-023950/logs/validator-repair.log
```

Validator log facts:

- The Validator Agent was launched with the full Validator system prompt.
- The task prompt required `reports/validator.v2.json`.
- The Agent timed out after 45 seconds in the test run.
- The workflow appended a `deterministic validator fallback` section to the log.

## Runner Repair Report

Report path:

```text
shared-tasks/investigation-maple-grouped-fallback-20260429-023950/reports/runner-repair.v2.json
```

Summary:

```json
{
  "mode": "deterministic_fallback",
  "reason": "runner_timeout: Runner repair timed out after 45 seconds",
  "source_attempt": 1,
  "target_attempt": 2,
  "changed_pages": [4, 6, 7]
}
```

Actions:

```json
[
  {
    "type": "mark_background_image",
    "page_number": 4,
    "element_id": "p4-image-2",
    "area_ratio": 0.8835555465133103
  },
  {
    "type": "mark_background_image",
    "page_number": 6,
    "element_id": "p6-image-7",
    "area_ratio": 0.7174093798596417
  },
  {
    "type": "mark_background_image",
    "page_number": 6,
    "element_id": "p6-image-10",
    "area_ratio": 0.7174093798596417
  },
  {
    "type": "mark_background_image_group",
    "page_number": 7,
    "element_id": "p7-image-2",
    "area_ratio": 0.44583000525881944
  },
  {
    "type": "mark_background_image_group",
    "page_number": 7,
    "element_id": "p7-image-3",
    "area_ratio": 0.44583000525881944
  }
]
```

## Validator Comparison

### Attempt 1

Report path:

```text
shared-tasks/investigation-maple-grouped-fallback-20260429-023950/reports/validator.v1.json
```

Summary:

```text
aggregate_status: repair_needed
page 1: pass, visual 0.9547, raster 0
page 2: pass, visual 0.9451, raster 0.4537
page 3: pass, visual 0.9185, raster 0.4571
page 4: repair_needed, visual 0.8723, raster 0.8933
page 5: pass, visual 0.9205, raster 0
page 6: repair_needed, visual 0.8783, raster 0.9012
page 7: repair_needed, visual 0.8680, raster 0.7505
```

### Attempt 2

Report path:

```text
shared-tasks/investigation-maple-grouped-fallback-20260429-023950/reports/validator.v2.json
```

Summary:

```text
aggregate_status: manual_review
page 1: pass, visual 0.9547, raster 0
page 2: pass, visual 0.9451, raster 0.4537
page 3: pass, visual 0.9185, raster 0.4571
page 4: manual_review, visual 0.8723, raster 0
page 5: pass, visual 0.9205, raster 0
page 6: manual_review, visual 0.8783, raster 0
page 7: manual_review, visual 0.8680, raster 0
```

Interpretation:

- The repair pass removed editability/raster failures from pages 4, 6, and 7.
- The remaining issue type is visual fidelity.
- The next phase should focus on region-level visual diff localization and controlled geometry repair.

## Verification

Fresh verification commands run after the changes:

```bash
cd apps/worker && .venv/bin/pytest -q
```

Result:

```text
174 passed, 5 warnings in 13.46s
```

Web tests:

```bash
npm --workspace apps/web run test -- --run
```

Result:

```text
Test Files 9 passed (9)
Tests 41 passed (41)
```

## Current Limitations

- The workflow still depends on Codex subprocess agents for optional repair and validation attempts; deterministic fallback prevents stalls but does not replace a purpose-built repair planner.
- Validator issues often lack page-local bounding boxes. This prevents Runner from making precise, bounded visual repairs.
- Remaining Maple failures are visual fidelity scores around 0.87 on pages 4, 6, and 7.
- Background classification is improved, but complex foreground diagrams and tables still need better editable reconstruction.
- The sample matrix has not yet been upgraded to compare generated PPTX structure against the ideal PPTX outputs in `pdf-to-ppt/example-output`.

## Next Phase

The next phase should be the visual-fidelity repair phase. Its goal is to move pages from `manual_review` to `pass` by adding region-level validation evidence and constrained repair actions for geometry, z-order, text placement, image cropping, table reconstruction, and shape/path generation.

The implementation plan is archived separately:

```text
docs/superpowers/plans/2026-04-29-pdf-to-ppt-visual-fidelity-next-phase.md
```
