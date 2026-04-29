# Maple Ideal PPTX Reverse Engineering Results

Date: 2026-04-29

## Task Directory

`shared-tasks/maple-ideal-reverse-20260429-155050`

## Generated Candidate Paths

- `output/candidate.v1.pptx`
- `output/candidate.v2.pptx`
- `output/final.pptx`

## Validator Summary

### Validator v1

Aggregate status: `repair_needed`

| Page | Status | Visual | Editable | Text | Raster | Issues |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 4 | manual_review | 0.8723 | 1.0 | 1.0 | 0.0000 | visual_fidelity |
| 6 | repair_needed | 0.8783 | 1.0 | 1.0 | 0.9012 | editability, visual_fidelity |
| 7 | repair_needed | 0.8680 | 1.0 | 1.0 | 0.7505 | editability, visual_fidelity |

### Validator v2

Aggregate status: `manual_review`

| Page | Status | Visual | Editable | Text | Raster | Issues |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 4 | manual_review | 0.8723 | 1.0 | 1.0 | 0.0000 | visual_fidelity |
| 6 | manual_review | 0.8783 | 1.0 | 1.0 | 0.0000 | visual_fidelity |
| 7 | manual_review | 0.8680 | 1.0 | 1.0 | 0.0000 | visual_fidelity |

## Ideal Strategy Summary

Report path: `reports/ideal-comparison.json`

| Page | Generated Strategy | Ideal Strategy | Picture Delta | Shape Delta | Text Box Delta | Largest Picture Delta | Coverage Delta |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 4 | fragmented_objects | background_plus_foreground_text | 11 | 20 | 17 | 0.000001 | -0.034380 |
| 6 | fragmented_objects | background_plus_foreground_text | 7 | 45 | 44 | -0.239341 | -0.056998 |
| 7 | fragmented_objects | background_plus_foreground_text | 6 | 36 | 34 | -0.385287 | -0.095253 |

Baseline comparison from `shared-tasks/next-phase-maple-20260429-031808` showed page 4 picture delta `17`. This run reduced page 4 picture delta to `11` while keeping page 4 visual score at `0.8723` and final aggregate status at `manual_review`. Strategy deltas use the XML inspection/profile counts; the report also includes `generated_pictures` and `ideal_pictures` from python-pptx as cross-check counts. The report includes `top_geometry_mismatches` per page to identify the largest normalized bbox gaps. Automatic background promotion now requires visible editable foreground after the image layer, so hidden watermark or foreground-image cases are not auto-declared as backgrounds.

## Acceptance Check

- Maple aggregate status did not regress below `manual_review`: final validator v2 aggregate is `manual_review`.
- Pages 4, 6, and 7 did not regress in text coverage: all remain `1.0` in validator v1 and v2.
- Generated-vs-ideal fragmentation improved on page 4: picture delta improved from baseline `17` to `11`.

## Verification Commands And Results

- `cd apps/worker && .venv/bin/pytest tests/test_runner_repair.py tests/test_pptx_inspect.py tests/test_pptx_strategy.py tests/test_compare_ideal_pptx.py tests/test_sample_discovery.py tests/test_pptx_generation.py tests/test_pdf_tools.py -q`
  - Result: `100 passed, 5 warnings`
- `TASK_DIR=shared-tasks/maple-ideal-reverse-20260429-155050 CODEX_AGENT_TIMEOUT_SECONDS=120 PYTHONPATH=apps/worker/src apps/worker/.venv/bin/python` running `run_pdf_to_ppt(Path(os.environ["TASK_DIR"]))`
  - Result: exited `0`, wrote `candidate.v1.pptx`, `candidate.v2.pptx`, `final.pptx`, `validator.v1.json`, and `validator.v2.json`
- `TASK_DIR=shared-tasks/maple-ideal-reverse-20260429-155050 PYTHONPATH=apps/worker/src apps/worker/.venv/bin/python` running `compare_pptx_structure(output/final.pptx, Maple ideal PPTX)`
  - Result: exited `0`, wrote `reports/ideal-comparison.json`
- `cd apps/worker && .venv/bin/pytest -q`
  - Result: `212 passed, 5 warnings`
- `npm --workspace apps/web run test -- --run`
  - Result: `9 passed` test files, `41 passed` tests
