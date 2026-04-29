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
7. Separate PDF background from foreground content. Do not fail a slide only because it contains a declared PDF background, but reject full-page screenshots and excessive raster fallback when foreground content is not editable.
8. Require foreground text, tables, formulas, diagrams, labels, callouts, shapes, and paths to be editable whenever evidence supports reconstruction.
9. Include region evidence for visual-fidelity issues whenever diff regions are available.
10. Include `repair_hints` for Runner when an issue maps to a supported constrained repair action.
11. Use `manual_review` when the page has remaining visual mismatch but no safe bounded repair hint.
12. Write strict `reports/validator.vN.json` with `evidence_paths`, scores, statuses, and repair instructions.
13. Recommend pass, repair, manual review, or failure from evidence only.
