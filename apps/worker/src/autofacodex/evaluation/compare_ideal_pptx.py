from pathlib import Path

from pptx import Presentation


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


def compare_pptx_structure(generated_path: Path, ideal_path: Path) -> dict:
    generated = Presentation(generated_path)
    ideal = Presentation(ideal_path)
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
        pages.append(
            {
                "page_number": index + 1,
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
