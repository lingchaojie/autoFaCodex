from autofacodex.contracts import PageValidation, ValidatorIssue, ValidatorReport


def build_validator_report(
    task_id: str,
    attempt: int,
    page_count: int,
    visual_scores: dict[int, float],
    editable_scores: dict[int, float],
    text_scores: dict[int, float],
    raster_ratios: dict[int, float],
) -> ValidatorReport:
    if page_count < 1:
        raise ValueError("page_count must be at least 1")

    pages: list[PageValidation] = []
    for page_number in range(1, page_count + 1):
        visual = visual_scores.get(page_number, 0)
        editable = editable_scores.get(page_number, 0)
        text = text_scores.get(page_number, 0)
        raster = raster_ratios.get(page_number, 1)
        issues: list[ValidatorIssue] = []
        status = "pass"
        if raster >= 0.5 or editable < 0.5:
            status = "repair_needed"
            issues.append(
                ValidatorIssue(
                    type="editability",
                    message="Slide contains excessive raster content or too few editable elements",
                    suggested_action="Reconstruct visible text and simple shapes as editable PPT elements",
                )
            )
        if visual < 0.9:
            status = "repair_needed"
            issues.append(
                ValidatorIssue(
                    type="visual_fidelity",
                    message="Rendered PPTX differs from the source PDF page",
                    suggested_action="Use the diff render to adjust positions, sizes, colors, and missing regions",
                )
            )
        if text < 0.8:
            status = "repair_needed"
            issues.append(
                ValidatorIssue(
                    type="text_coverage",
                    message="Editable PPTX text does not cover source PDF text",
                    suggested_action="Recover missing text as editable text boxes",
                )
            )
        pages.append(
            PageValidation(
                page_number=page_number,
                status=status,
                visual_score=visual,
                editable_score=editable,
                text_coverage_score=text,
                raster_fallback_ratio=raster,
                issues=issues,
            )
        )
    return ValidatorReport(task_id=task_id, attempt=attempt, pages=pages)
