# PDF To PPT Next Sample Baseline Design

Date: 2026-04-29

## Goal

Select the next non-Maple PDF-to-PPT improvement target from data, not guesswork.
The baseline pass will run both remaining sample decks through the current Maple PR
tooling and compare generated PPTX output with the supplied ideal PPTX files.

Candidate samples:

- `清博空天BP Final`
- `20260110.无穹创新BP_v27-仅供隐山资本参考`

## Scope

This pass produces evaluation evidence and a next-target recommendation only. It
does not implement new conversion or repair behavior.

Included:

- Run both candidate PDFs through the existing `run_pdf_to_ppt` workflow.
- Generate validator reports for each candidate.
- Generate generated-vs-ideal PPTX structure comparisons for each candidate.
- Archive a concise ranking summary with the selected next target and first
  problem pages.
- Use the Maple PR branch as the baseline because it contains the latest PPTX
  inspection and ideal-comparison tooling.

Excluded:

- New repair heuristics.
- Changes to scoring thresholds.
- Sample-specific hardcoding.
- Merging or changing PR #3.

## Branch And Workspace

Create and work in an isolated branch:

- Branch: `feature/pdf-ppt-next-baseline`
- Base: `feature/maple-ideal-reverse`
- Worktree: `.worktrees/pdf-ppt-next-baseline`

This keeps the next-sample baseline dependent on PR #3 intentionally and makes
the dependency visible in branch history.

## Data Flow

1. Discover the two candidate PDF files from `pdf-to-ppt/pdf-source`.
2. Create one task directory per sample under `shared-tasks/`.
3. Copy each PDF to `input.pdf`.
4. Run `run_pdf_to_ppt(task_dir)`.
5. Read the latest `validator.v*.json`.
6. Compare `output/final.pptx` to the matching ideal PPTX from
   `pdf-to-ppt/example-output` with `compare_pptx_structure`.
7. Write per-sample reports plus one archive summary.

## Ranking Criteria

The next target is the sample with the strongest combination of:

- More `repair_needed` or `manual_review` pages.
- Lower minimum visual score.
- Lower average visual score.
- More pages with raster fallback or editability issues.
- Larger generated-vs-ideal object deltas, especially picture, shape, and text
  box deltas on pages with poor visual scores.

If the metrics conflict, prioritize pages where visual fidelity is poor while
text coverage remains high. Those pages are more likely to benefit from
structure/layout improvements without needing OCR or text extraction changes.

## Error Handling

- If one sample fails conversion, keep the successful sample result and record
  the failure with the exception message and task directory.
- If ideal comparison fails for a sample, keep validator evidence and record the
  comparison failure separately.
- If both samples fail, stop and treat that as a pipeline regression before
  planning any visual-fidelity work.
- Do not delete existing user sample files.

## Outputs

The baseline pass should produce:

- Two task directories under `shared-tasks/`.
- `output/final.pptx` for each successful sample.
- `reports/validator.v*.json` for each successful sample.
- `reports/ideal-comparison.json` for each successful ideal comparison.
- Archive document:
  `docs/superpowers/archives/2026-04-29-pdf-ppt-next-sample-baseline-results.md`

The archive must include:

- Task directory paths.
- Per-sample aggregate status.
- Page counts for `pass`, `manual_review`, `repair_needed`, and `failed`.
- Min and average visual score.
- Text coverage, editability, and raster fallback summary.
- Pages with the largest structure deltas.
- The selected next target and why it was selected.
- Verification commands and exact results.

## Testing

Before calling the baseline complete, run:

- `cd apps/worker && .venv/bin/pytest -q`
- `npm --workspace apps/web run test -- --run`

For any helper added during implementation, add focused tests before using it in
the baseline workflow. If no helper is added, the baseline can be verified by
the existing full suites plus the generated reports.

## Review Gate

After the archive is written, review the ranking against the raw validator and
ideal-comparison JSON before choosing the next target. The next implementation
plan should only start after that target and its first problem pages are named.
