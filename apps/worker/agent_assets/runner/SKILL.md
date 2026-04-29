---
name: pdf-to-ppt-runner
description: Repair editable PDF to PPT slide models from Validator reports.
---

# PDF To PPT Runner Skill

1. Read `task-manifest.json`.
2. Read the latest `reports/validator.vN.json`.
3. Identify pages with `repair_needed` or `manual_review`.
4. Read only the relevant `evidence_paths`, slide model pages, PDF extraction data, and user messages.
5. Update editable elements in `slides/slide-model.vN.json`; do not hard-code sample-specific layouts.
6. Separate PDF background from foreground content. Mark genuine full-slide PDF background images or color blocks with `style.role = "background"`, keep them behind foreground elements, and never use them to cover missing foreground structure.
7. Rebuild foreground text, tables, formulas, diagrams, labels, callouts, shapes, and paths as editable PowerPoint elements whenever possible. Use `table` elements with `style.rows` for grid-like content and `path` elements with normalized `style.points` for simple freeform geometry. Use `semantic_table` overlays only when a visible table would degrade visual fidelity.
8. Do not manually decide that a hidden `semantic_table` overlay is safe to show. The guarded semantic table repair tool or Validator must compare visual scores before promotion.
9. Avoid full-page screenshots and record any bounded raster fallback region.
10. Prefer constrained repair actions from Validator `repair_hints` before free-form slide-model edits.
11. Use only supported constrained repair action names unless the task explicitly asks for a new action implementation.
12. Record each constrained repair action in `reports/runner-repair.vN.json` with action name, page number, issue type, changed element ids, and remaining risk.
13. Regenerate the PPTX through the provided tool command.
14. If a confident semantic repair is not possible, perform a no-op repair: copy the latest slide model to the required target version, still generate the required target PPTX, and explain the reason in `reports/runner-repair.vN.json`.
15. Write `reports/runner-repair.vN.json` and a concise task event.
16. Stop after one bounded repair pass so the Validator can re-score from real evidence.
