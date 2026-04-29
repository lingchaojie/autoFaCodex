# Maple Ideal PPTX Reverse Engineering Design

Date: 2026-04-29

## Context

The current PDF-to-PPT workflow converts the Maple sample to an editable PPTX and clears the earlier editability/raster failures. The remaining Maple pages 4, 6, and 7 stay at `manual_review` because their visual scores remain below the pass threshold:

- Page 4: visual `0.8723`, localized diff region `[0.0005, 0.6306, 0.6677, 1.0]`
- Page 6: visual `0.8783`, localized diff region `[0.2057, 0.2296, 0.2427, 0.3009]`
- Page 7: visual `0.8680`, localized diff region `[0.5948, 0.3185, 0.9396, 0.3278]`

The ideal Maple PPTX uses a hybrid strategy: complex visual content is represented by fewer, larger background-like pictures, while meaningful foreground text remains editable. The generated PPTX currently keeps many more fragmented images and shapes than the ideal deck. That difference is now more important than adding another generic bounding-box repair.

## Goal

Reverse engineer the Maple ideal PPTX object strategy and use it to guide the next implementation phase toward PPTX output that is structurally closer to the ideal deck, especially on pages 4, 6, and 7.

## Non-Goals

- Do not attempt to hand-author Maple-specific slide content.
- Do not claim pixel-perfect reconstruction.
- Do not expand to the other two sample decks in this phase.
- Do not weaken editability validation to make current output pass.
- Do not replace the existing PDF extraction and PPTX generation pipeline.

## Recommended Approach

Use an ideal-first profiling loop for the Maple sample.

1. Add an ideal PPTX strategy profiler that extracts page-level and object-level evidence from the Maple ideal deck.
2. Compare generated and ideal decks using object counts, geometry distributions, background coverage, and foreground text structure.
3. Use the profiler output to drive model-builder changes that reduce unnecessary image/shape fragmentation while preserving editable foreground text.
4. Accept changes only when Maple structure deltas improve and validator status does not regress.

This approach directly matches the selected direction: understand the ideal PPTX first, then adjust conversion behavior from evidence.

## Alternatives Considered

### Page-Specific Visual Repair Loop

This would use current diff regions to add geometry, crop, or z-order repair actions for pages 4, 6, and 7. It is direct and score-focused, but it risks optimizing isolated symptoms without understanding why the ideal deck has a simpler object strategy.

### Full Sample Matrix First

This would run and analyze all three sample PDFs before changing Maple. It would improve breadth, but it delays useful changes to the best-instrumented sample and increases the chance of designing an over-general fix too early.

## Architecture

### Ideal Strategy Profiler

Add a profiler around existing PPTX inspection code. It should report, per slide:

- slide size
- text run count and grouped text box count
- picture count
- shape count
- table count
- largest picture area ratio
- total picture area ratio
- picture coverage ratio
- full-page or near-full-page background candidates
- picture and shape geometry lists
- page-level strategy classification

The strategy classification should be deterministic and simple:

- `background_plus_foreground_text`: large picture coverage with editable text above it
- `fragmented_objects`: many small images or shapes without a dominant background
- `mostly_editable`: low picture coverage and substantial text/shape content
- `unknown`: insufficient evidence

### Generated-vs-Ideal Comparison

Extend the existing ideal comparison so it can explain differences, not just count them. For Maple pages 4, 6, and 7, it should report:

- generated and ideal strategy classification
- object count deltas
- background coverage deltas
- largest picture ratio deltas
- text grouping deltas
- top geometry mismatches by normalized bounding box

This report becomes the evidence source for implementation choices and archive notes.

### Model Builder Adjustments

Use profiler evidence to adjust `slide_model_builder` conservatively:

- Promote dominant complex regions to background-style images when the ideal page uses the same strategy.
- Suppress or de-emphasize duplicated image fragments when they overlap a promoted background region and do not add unique foreground text.
- Preserve extracted foreground text as editable elements above the background.
- Preserve small semantic assets, such as logos and visible foreground icons, unless they are fully covered by a promoted background.
- Keep these heuristics general, but gate them initially through Maple evidence and regression tests.

### Validation Loop

After each candidate implementation, run Maple through the existing workflow and compare:

- validator v1/v2 aggregate status
- per-page visual scores for pages 4, 6, and 7
- raster fallback ratio
- text coverage score
- generated-vs-ideal structure deltas

A change is acceptable only if it reduces generated-vs-ideal fragmentation and does not regress editability, text coverage, or aggregate status.

## Data Flow

1. Maple PDF is converted by the existing workflow into slide model and generated PPTX.
2. The ideal Maple PPTX is inspected by the new profiler.
3. The generated PPTX is inspected by the same profiler.
4. The comparison report identifies where generated strategy diverges from ideal strategy.
5. Model-builder heuristics use those findings to produce a less fragmented candidate.
6. Validator and ideal comparison reports are archived for review.

## Error Handling

- If the ideal PPTX is missing, the profiler returns a clear missing-file error and the sample evaluation records `ideal_comparison: null`.
- If PPTX XML cannot be parsed, the profiler reports the slide and XML part that failed.
- If image geometry is missing, that object is counted but excluded from area and coverage calculations.
- If strategy classification is ambiguous, the profiler uses `unknown` and does not trigger model-builder heuristics from that page.
- If a model-builder heuristic would remove all editable foreground text from a slide, it is skipped.

## Testing

Unit tests should cover:

- profiler classification for background-plus-text, fragmented, and mostly-editable slides
- generated-vs-ideal comparison fields for object counts and strategy deltas
- missing ideal PPTX behavior
- model-builder suppression of duplicated image fragments while preserving text
- model-builder no-op behavior when ideal strategy is unknown

Regression verification should cover:

- Maple workflow produces `candidate.v1.pptx`, `candidate.v2.pptx`, `final.pptx`, validator reports, and ideal comparison reports
- Maple pages 4, 6, and 7 do not regress in editability, text coverage, or aggregate status
- generated-vs-ideal object fragmentation decreases on at least one of pages 4, 6, or 7

## Success Criteria

- A machine-readable Maple ideal strategy report exists.
- The report explains why the ideal pages 4, 6, and 7 use fewer images/shapes than generated output.
- The generated-vs-ideal comparison exposes actionable strategy deltas.
- At least one model-builder change is backed by ideal strategy evidence.
- Maple remains at least `manual_review`; no page regresses to `repair_needed`.
- Structure deltas move closer to the ideal deck on at least one remaining manual-review page.

## Open Decisions Resolved

- Scope is Maple only for this phase.
- Ideal PPTX reverse engineering comes before another visual diff repair loop.
- The implementation plan will be written after this design is reviewed.
