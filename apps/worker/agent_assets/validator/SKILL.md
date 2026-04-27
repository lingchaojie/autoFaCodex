---
name: pdf-to-ppt-validator
description: Validate PDF to PPT outputs for visual fidelity, editability, and text coverage.
---

# PDF To PPT Validator Skill

1. Render source PDF pages or verify existing source renders.
2. Render the candidate PPTX pages.
3. Compare every PDF/PPTX page pair visually.
4. Inspect PPTX internals for editable text, shapes, tables, images, largest picture ratio, and full-page picture usage.
5. Compare source PDF text against editable PPTX text.
6. Write diagnostic diff and compare image paths.
7. Reject full-page screenshots and excessive raster fallback.
8. Write strict `reports/validator.vN.json` with `evidence_paths`, scores, statuses, and repair instructions.
9. Recommend pass, repair, manual review, or failure from evidence only.
