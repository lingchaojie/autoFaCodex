# PDF PPT Next Sample Baseline Results

Date: 2026-04-29

## Inputs

- Qingbo PDF: `/home/alvin/AutoFaCodex/pdf-to-ppt/pdf-source/清博空天BP Final.pdf`
- Qingbo ideal PPTX: `/home/alvin/AutoFaCodex/pdf-to-ppt/example-output/清博空天BP Final.pptx`
- Wuqiong PDF: `/home/alvin/AutoFaCodex/pdf-to-ppt/pdf-source/20260110.无穹创新BP_v27-仅供隐山资本参考.pdf`
- Wuqiong ideal PPTX: `/home/alvin/AutoFaCodex/pdf-to-ppt/example-output/20260110.无穹创新BP_v27-仅供隐山资本参考.pptx`

## Task Directories

- Qingbo: `shared-tasks/next-baseline-qingbo-20260429`
- Wuqiong: `shared-tasks/next-baseline-wuqiong-20260429`

## Sample Summary

| Sample | Aggregate | Pages | Pass | Manual Review | Repair Needed | Failed | Avg Visual | Min Visual | Issues | Raster Pages |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 清博空天BP Final | repair_needed | 18 | 2 | 5 | 11 | 0 | 0.8666 | 0.6968 | editability:5, visual_fidelity:13 | 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17 |
| 20260110.无穹创新BP_v27-仅供隐山资本参考 | repair_needed | 20 | 1 | 2 | 17 | 0 | 0.8056 | 0.6524 | editability:13, visual_fidelity:18 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20 |

## 清博空天BP Final Lowest Visual Pages

| Page | Status | Visual | Text | Editable | Raster | Issues |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | repair_needed | 0.6968 | 1.0 | 1.0 | 0.0000 | visual_fidelity |
| 2 | repair_needed | 0.7627 | 1.0 | 1.0 | 0.0685 | visual_fidelity |
| 14 | repair_needed | 0.8026 | 1.0 | 1.0 | 0.2598 | visual_fidelity |
| 13 | repair_needed | 0.8144 | 1.0 | 1.0 | 0.2233 | visual_fidelity |
| 4 | repair_needed | 0.8482 | 1.0 | 1.0 | 0.1943 | visual_fidelity |

## 清博空天BP Final Largest Structure Deltas

| Page | Generated Strategy | Ideal Strategy | Picture Delta | Shape Delta | Text Box Delta | Picture Coverage Delta |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| 10 | fragmented_objects | unknown | 55 | 52 | 49 | 0.036245 |
| 2 | fragmented_objects | mostly_editable | 3 | 65 | 67 | -0.003767 |
| 4 | fragmented_objects | mostly_editable | 4 | 66 | 61 | 0.011350 |
| 5 | fragmented_objects | unknown | 7 | 65 | 44 | -0.060434 |
| 3 | fragmented_objects | unknown | 1 | 74 | 32 | -0.001424 |

## 20260110.无穹创新BP_v27-仅供隐山资本参考 Lowest Visual Pages

| Page | Status | Visual | Text | Editable | Raster | Issues |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | repair_needed | 0.6524 | 1.0 | 1.0 | 0.6672 | editability, visual_fidelity |
| 11 | repair_needed | 0.6864 | 1.0 | 1.0 | 0.5197 | editability, visual_fidelity |
| 3 | repair_needed | 0.7106 | 1.0 | 1.0 | 0.5197 | editability, visual_fidelity |
| 4 | repair_needed | 0.7262 | 1.0 | 1.0 | 0.5608 | editability, visual_fidelity |
| 7 | repair_needed | 0.7627 | 0.9849397590361446 | 1.0 | 0.5530 | editability, visual_fidelity |

## 20260110.无穹创新BP_v27-仅供隐山资本参考 Largest Structure Deltas

| Page | Generated Strategy | Ideal Strategy | Picture Delta | Shape Delta | Text Box Delta | Picture Coverage Delta |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| 2 | fragmented_objects | fragmented_objects | -2 | 89 | 91 | 0.090929 |
| 11 | fragmented_objects | unknown | 16 | 74 | 72 | -0.271789 |
| 4 | fragmented_objects | background_plus_foreground_text | 60 | 50 | 39 | -0.439245 |
| 10 | fragmented_objects | fragmented_objects | 22 | 66 | 61 | 0.027093 |
| 15 | fragmented_objects | fragmented_objects | 9 | -93 | 38 | 0.198663 |

## Recommendation

Recommended next target: `20260110.无穹创新BP_v27-仅供隐山资本参考`.

First problem pages to inspect: 1, 11, 3.

Reason: this sample ranks highest by combined manual-review/repair-needed page count, minimum visual score, average visual score, raster fallback pages, and generated-vs-ideal structure deltas.

## Verification Commands And Results

- `cd apps/worker && .venv/bin/pytest -q`
  - Result: `212 passed, 5 warnings`
- `npm --workspace apps/web run test -- --run`
  - Result: `9 passed` test files, `41 passed` tests
- Qingbo workflow command from Task 2 Step 2
  - Result: exited `0`, wrote `output/final.pptx` and validator reports.
- Qingbo ideal comparison command from Task 2 Step 3
  - Result: exited `0`, wrote `reports/ideal-comparison.json`.
- Wuqiong workflow command from Task 3 Step 2
  - Result: exited `0`, wrote `output/final.pptx` and validator reports.
- Wuqiong ideal comparison command from Task 3 Step 3
  - Result: exited `0`, wrote `reports/ideal-comparison.json`.
