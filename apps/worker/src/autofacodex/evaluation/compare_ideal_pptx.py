from pathlib import Path

from pptx import Presentation

from autofacodex.evaluation.pptx_strategy import profile_pptx_strategy


def _slide_counts(slide) -> dict[str, int]:
    text_runs = 0
    pictures = 0
    shapes = 0
    tables = 0
    for shape in slide.shapes:
        if getattr(shape, "has_text_frame", False) and shape.text_frame.text.strip():
            text_runs += 1
        if shape.shape_type == 13:
            pictures += 1
        if getattr(shape, "has_table", False):
            tables += 1
        shapes += 1
    return {
        "text_runs": text_runs,
        "pictures": pictures,
        "shapes": shapes,
        "tables": tables,
    }


def _profile_by_page(profile: dict) -> dict[int, dict]:
    return {
        int(page["page_number"]): page
        for page in profile.get("pages", [])
        if page.get("page_number") is not None
    }


def _profile_number(page: dict, field: str) -> float:
    try:
        return float(page.get(field, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _profile_int(page: dict, field: str) -> int:
    return int(_profile_number(page, field))


def _strategy_delta(generated_page: dict, ideal_page: dict) -> dict:
    return {
        "generated_strategy": generated_page.get("strategy", "unknown"),
        "ideal_strategy": ideal_page.get("strategy", "unknown"),
        "strategy_matches": generated_page.get("strategy") == ideal_page.get("strategy"),
        "picture_count_delta": _profile_int(generated_page, "pictures")
        - _profile_int(ideal_page, "pictures"),
        "shape_count_delta": _profile_int(generated_page, "shapes")
        - _profile_int(ideal_page, "shapes"),
        "text_box_count_delta": _profile_int(generated_page, "text_box_count")
        - _profile_int(ideal_page, "text_box_count"),
        "largest_picture_area_ratio_delta": round(
            _profile_number(generated_page, "largest_picture_area_ratio")
            - _profile_number(ideal_page, "largest_picture_area_ratio"),
            6,
        ),
        "picture_coverage_ratio_delta": round(
            _profile_number(generated_page, "picture_coverage_ratio")
            - _profile_number(ideal_page, "picture_coverage_ratio"),
            6,
        ),
    }


def compare_pptx_structure(generated_path: Path, ideal_path: Path) -> dict:
    generated = Presentation(generated_path)
    ideal = Presentation(ideal_path)
    generated_profiles = _profile_by_page(profile_pptx_strategy(generated_path))
    ideal_profiles = _profile_by_page(profile_pptx_strategy(ideal_path))
    page_count = max(len(generated.slides), len(ideal.slides))
    pages: list[dict] = []
    for index in range(page_count):
        generated_counts = (
            _slide_counts(generated.slides[index])
            if index < len(generated.slides)
            else {"text_runs": 0, "pictures": 0, "shapes": 0, "tables": 0}
        )
        ideal_counts = (
            _slide_counts(ideal.slides[index])
            if index < len(ideal.slides)
            else {"text_runs": 0, "pictures": 0, "shapes": 0, "tables": 0}
        )
        generated_profile = generated_profiles.get(index + 1, {})
        ideal_profile = ideal_profiles.get(index + 1, {})
        pages.append(
            {
                "page_number": index + 1,
                **_strategy_delta(generated_profile, ideal_profile),
                "generated_text_runs": generated_counts["text_runs"],
                "ideal_text_runs": ideal_counts["text_runs"],
                "generated_pictures": generated_counts["pictures"],
                "ideal_pictures": ideal_counts["pictures"],
                "generated_shapes": generated_counts["shapes"],
                "ideal_shapes": ideal_counts["shapes"],
                "generated_tables": generated_counts["tables"],
                "ideal_tables": ideal_counts["tables"],
            }
        )
    return {
        "generated_slide_count": len(generated.slides),
        "ideal_slide_count": len(ideal.slides),
        "slide_count_delta": len(generated.slides) - len(ideal.slides),
        "pages": pages,
    }
