---
name: pdf-to-ppt-runner
description: Repair editable PDF to PPT slide models from Validator reports.
---

# PDF To PPT Runner Skill

1. Read the task manifest.
2. Read the latest Validator report.
3. Identify pages with `repair_needed` or `manual_review`.
4. Inspect only the relevant slide model, PDF extraction data, and render artifacts.
5. Update editable elements in the slide model.
6. Avoid full-page screenshots.
7. Regenerate the PPTX through the provided tool command.
8. Record what changed and why.
