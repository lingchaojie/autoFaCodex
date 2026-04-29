# PDF To PPT Visual Fidelity Next Phase Results

Date: 2026-04-29

## Task Directory

`/home/alvin/AutoFaCodex/.worktrees/pdf-to-ppt-mvp/shared-tasks/next-phase-maple-20260429-031808`

The first Maple run exposed that `extract_diff_regions` was too conservative for real page diffs. It found no regions at `threshold=0.1, min_area_ratio=0.01`, even though lower thresholds found localized evidence. The Validator call was adjusted to use `threshold=0.05, min_area_ratio=0.001`, then the Maple workflow was rerun from a fresh task directory listed above.

## Generated Candidate Paths

- `output/candidate.v1.pptx`
- `output/candidate.v2.pptx`
- `output/final.pptx`

## Validator v1 Summary

Aggregate status: `repair_needed`

| Page | Status | Visual | Editable | Text | Raster | Issues | Region Evidence |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | pass | 0.9547 | 1.0 | 1.0 | 0.0000 | none | none |
| 2 | pass | 0.9451 | 1.0 | 1.0 | 0.4537 | none | none |
| 3 | pass | 0.9185 | 1.0 | 1.0 | 0.4571 | none | none |
| 4 | repair_needed | 0.8723 | 1.0 | 1.0 | 0.8933 | editability, visual_fidelity | `[0.0005, 0.6306, 0.6677, 1.0]` |
| 5 | pass | 0.9205 | 1.0 | 1.0 | 0.0000 | none | none |
| 6 | repair_needed | 0.8783 | 1.0 | 1.0 | 0.9012 | editability, visual_fidelity | `[0.2057, 0.2296, 0.2427, 0.3009]` |
| 7 | repair_needed | 0.8680 | 1.0 | 1.0 | 0.7505 | editability, visual_fidelity | `[0.5948, 0.3185, 0.9396, 0.3278]` |

## Validator v2 Summary

Aggregate status: `manual_review`

| Page | Status | Visual | Editable | Text | Raster | Issues | Region Evidence |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | pass | 0.9547 | 1.0 | 1.0 | 0.0000 | none | none |
| 2 | pass | 0.9451 | 1.0 | 1.0 | 0.4537 | none | none |
| 3 | pass | 0.9185 | 1.0 | 1.0 | 0.4571 | none | none |
| 4 | manual_review | 0.8723 | 1.0 | 1.0 | 0.0000 | visual_fidelity | `[0.0005, 0.6306, 0.6677, 1.0]` |
| 5 | pass | 0.9205 | 1.0 | 1.0 | 0.0000 | none | none |
| 6 | manual_review | 0.8783 | 1.0 | 1.0 | 0.0000 | visual_fidelity | `[0.2057, 0.2296, 0.2427, 0.3009]` |
| 7 | manual_review | 0.8680 | 1.0 | 1.0 | 0.0000 | visual_fidelity | `[0.5948, 0.3185, 0.9396, 0.3278]` |

## Runner Repair Actions

Runner timed out after 120 seconds, so the deterministic fallback ran.

- Page 4: `mark_background_image` on `p4-image-2`
- Page 6: `mark_background_image` on `p6-image-7`
- Page 6: `mark_background_image` on `p6-image-10`
- Page 7: `mark_background_image_group` on `p7-image-2`
- Page 7: `mark_background_image_group` on `p7-image-3`

Result: editability/raster failures on pages 4, 6, and 7 were cleared. Visual scores did not improve, so those pages remain `manual_review` with localized visual-fidelity region evidence and `repair_hints`.

## Remaining Manual Review Pages

- Page 4: `visual_fidelity`, visual score `0.8723`
- Page 6: `visual_fidelity`, visual score `0.8783`
- Page 7: `visual_fidelity`, visual score `0.8680`

## Verification Commands And Results

- `cd apps/worker && .venv/bin/pytest tests/test_validate_candidate.py tests/test_visual_diff_regions.py -q`
  - Result: `12 passed, 5 warnings`
- `TASK_DIR=... CODEX_AGENT_TIMEOUT_SECONDS=120 PYTHONPATH=apps/worker/src apps/worker/.venv/bin/python - <<'PY' ... run_pdf_to_ppt(...) ... PY`
  - Result: exited `0`, wrote `candidate.v1.pptx`, `candidate.v2.pptx`, `final.pptx`, `validator.v1.json`, `validator.v2.json`, and `runner-repair.v2.json`
- `cd apps/worker && .venv/bin/pytest -q`
  - Result: `184 passed, 5 warnings`
- `npm --workspace apps/web run test -- --run`
  - Result: `9 passed` test files, `41 passed` tests
