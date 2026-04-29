---
name: pdf-to-ppt-runner
description: Repair editable PDF to PPT slide models from Validator reports.
---

# PDF To PPT Runner Skill

1. Read `task-manifest.json`.
2. Read the latest `reports/validator.vN.json`.
3. Identify pages with `repair_needed` or `manual_review`.
4. Read only the relevant `evidence_paths`, slide model pages, PDF extraction data, and user messages.
5. Update editable elements in `slides/slide-model.vN.json`.
6. Avoid full-page screenshots and record any bounded raster fallback region.
7. Regenerate the PPTX through the provided tool command.
8. Write `reports/runner-repair.vN.json` and a concise task event.
9. Stop after one bounded repair pass so the Validator can re-score from real evidence.
