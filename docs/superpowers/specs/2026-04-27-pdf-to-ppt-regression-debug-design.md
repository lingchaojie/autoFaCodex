# PDF To Editable PPT Regression Debug Design

Date: 2026-04-27

## Summary

This design defines the next phase of the PDF to editable PPT workflow: a regression-driven debugging loop that improves general conversion quality across all sample PDFs, rather than tuning output for one PDF.

The system must convert PDFs into PPTX files made from editable PowerPoint elements. Full-page screenshots are invalid as final output. The quality gate is based on real rendered evidence: source PDF page renders, candidate PPTX renders, visual diffs, PPTX structure inspection, and editable text coverage.

## Goals

- Run every PDF in `pdf-to-ppt-test-samples/` as a regression sample.
- Measure every page with real rendering and structured validation.
- Use the regression report to prioritize general conversion improvements.
- Keep output PPTX files editable: text boxes, images, shapes, tables, paths, and bounded raster fallback regions only when necessary.
- Improve Runner and Validator prompts and skills so agents use evidence and tools instead of self-certifying quality.
- Prevent PDF-specific rules based on sample filenames, exact page numbers, or hard-coded text content.

## Quality Bar

The target quality bar is:

- Each page should reach visual similarity `>= 0.90`.
- No page should be accepted below `0.85` without explicit `manual_review`.
- Source PDF text should appear as editable PPT text whenever it is extractable.
- Full-page screenshot slides are hard failures.
- High raster fallback ratio is a hard failure unless the page is explicitly marked for manual review.
- Every pass decision must cite evidence paths for renders, diffs, PPTX inspection, and text coverage.

These thresholds are validation targets, not a claim that arbitrary real-world PDFs will be perfectly reconstructed in the first implementation pass.

## Current State

The MVP worktree already contains:

- Deterministic PDF extraction with text, images, simple drawings, fonts, colors, and page geometry.
- Initial slide model generation.
- PPTX generation through `python-pptx`.
- Basic PPTX editability inspection.
- Runner and Validator agent prompt/skill assets.
- Initial and repair workflow entry points.
- Sample task outputs under `shared-tasks/`.

The current gap is that initial validation still uses placeholder scores in the workflow. A real local run on the Maple sample produced editable PPTX elements, but visual similarity was not consistently high enough. This means the next phase must make validation evidence real before optimizing conversion behavior.

## Approach

Use a full-sample regression matrix as the outer loop:

```text
all sample PDFs
  -> task directories
  -> deterministic conversion
  -> PPTX rendering
  -> visual diff
  -> editability inspection
  -> text coverage check
  -> aggregate regression report
  -> prioritize general fixes
```

Each conversion task keeps the existing workflow shape:

```text
PDF
  -> extract objects
  -> build editable slide model
  -> generate PPTX
  -> render candidate
  -> validate visual/editability/text coverage
  -> repair slide model
  -> regenerate and revalidate
```

The Validator is the only authority for pass, repair, manual review, or failure. Runner repairs must be scoped to Validator evidence and should modify the slide model rather than hand-editing generated PPTX files.

## Tools

### `evaluate_samples`

Runs all PDFs in `pdf-to-ppt-test-samples/` and writes an aggregate report. The report includes per-sample and per-page visual scores, editable scores, text coverage scores, raster fallback ratios, issue counts, output paths, and before/after deltas.

This tool is the primary regression command for PDF to PPT quality work.

### `render_pptx`

Renders a PPTX to PDF and PNG page images using LibreOffice plus the existing PDF renderer. It must configure writable LibreOffice profile/runtime directories so rendering works in local, sandboxed, and container contexts. It must preserve stdout, stderr, exit codes, rendered PDF paths, and rendered page paths as evidence.

### `validate_candidate`

Validates one task attempt from real evidence. Inputs include source PDF renders, candidate PPTX renders, the candidate PPTX file, extracted PDF metadata, and the slide model. Output is `reports/validator.vN.json`.

This replaces placeholder validation in the initial workflow.

### `inspect_pptx_editability`

Expands the existing PPTX inspection from simple counts into page-level structure evidence:

- editable text content and text run count
- picture count and picture bounding boxes
- shape count and shape bounding boxes
- table and path counts when supported
- largest image area ratio
- full-page image detection
- total raster fallback area ratio from slide model metadata

### `text_coverage`

Compares source PDF text with editable PPT text. The first implementation should normalize whitespace and punctuation enough to handle PDF text extraction fragmentation. Later iterations can add OCR or visual text checks for scanned or flattened documents.

### Diagnostics Output

Every validation attempt should write enough artifacts for humans and agents to inspect the failure:

- PDF reference render
- PPTX render
- visual diff image
- side-by-side compare image when practical
- issue regions where detectable
- PPTX structure inspection JSON
- text coverage JSON

## Prompt And Skill Changes

### Runner

Runner instructions must make evidence-based slide model repair explicit:

- Read latest `reports/validator.vN.json` first.
- Treat Validator report as the source of truth.
- Repair only Validator-identified pages or regions unless a global issue is proven.
- Update `slides/slide-model.vN.json` as the primary repair surface.
- Regenerate PPTX through the deterministic generation tool.
- Keep output editable and reject full-page screenshot workarounds.
- Use bounded raster fallback only with a reason and measured region.
- Write `reports/runner-repair.vN.json` with changed pages, changed elements, evidence used, tools run, files written, fallback decisions, and remaining risks.

Runner must not validate its own output or claim success.

### Validator

Validator instructions must make strict evidence-based judgment explicit:

- Validate every page exactly once.
- Use rendered PDF and PPTX pages for visual scoring.
- Use PPTX inspection for editability scoring.
- Use source-vs-editable text comparison for text coverage scoring.
- Reject full-page screenshot slides and high raster fallback ratios.
- Include evidence paths and actionable repair instructions.
- Mark pages as `manual_review` or `failed` when evidence is missing or insufficient.
- Write strict JSON matching the Validator contract.

Validator must not accept Runner confidence as evidence.

## Optimization Strategy

Optimization proceeds by highest general impact:

1. Replace placeholder validation with real rendering, diffing, editability inspection, and text coverage.
2. Stabilize LibreOffice rendering locally and in containers.
3. Generate a full-sample baseline report.
4. Identify the most frequent failure classes across all samples.
5. Fix deterministic reconstruction behavior by category: coordinates, fonts, z-order, backgrounds, image placement/cropping, rectangles, paths, tables, and fallback accounting.
6. Update Runner and Validator prompts/skills so agent repairs use the new evidence.
7. Re-run the full sample matrix after each change and report improvements and regressions.

All fixes must be explainable as general PDF reconstruction improvements.

## Non-Goals

- Perfect reconstruction of every arbitrary PDF in the first pass.
- Commercial conversion services as required dependencies.
- Sample-specific rules based on filenames, exact page numbers, or known sample text.
- Accepting visually close full-page screenshots as editable output.
- AI-driven full-page redraw as the default conversion strategy.

## Testing And Verification

Unit tests should cover:

- PPTX rendering command behavior and error reporting.
- Real Validator report generation from fixture renders.
- Full-page image detection.
- Raster fallback ratio calculation.
- Editable text extraction from PPTX.
- Source-vs-PPT text coverage.
- Aggregate sample report schema and sorting.

Regression verification should run:

```bash
cd apps/worker && .venv/bin/pytest -q
npm --workspace apps/web run test -- --run
PYTHONPATH=apps/worker/src apps/worker/.venv/bin/python -m autofacodex.evaluation.run_samples
```

The final sample command may evolve into a dedicated `evaluate_samples` CLI, but the requirement remains the same: every sample PDF must be converted and validated from real evidence.

## Open Implementation Notes

- The implementation must preserve existing user or worktree changes and should stage only intentional files.
- Existing sample artifacts under `shared-tasks/` are evidence but should not be treated as source of truth for future validation.
- If LibreOffice cannot run inside the normal sandbox, the tool should use explicit writable profile paths before requiring external escalation.
