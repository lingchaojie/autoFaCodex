from autofacodex.evaluation.pptx_strategy import (
    classify_slide_strategy,
    profile_pptx_strategy_from_inspection,
)


def test_classify_slide_strategy_background_plus_foreground_text():
    page = {
        "text_box_count": 3,
        "pictures": 3,
        "shapes": 8,
        "tables": 0,
        "largest_picture_area_ratio": 0.94,
        "total_picture_area_ratio": 1.0,
        "picture_coverage_ratio": 0.95,
        "picture_geometries": [{"x": 0, "y": 0, "w": 13.333, "h": 7.5}],
        "shape_geometries": [],
        "text_box_geometries": [{"x": 1, "y": 1, "w": 4, "h": 0.5}],
        "size": {"width": 13.333, "height": 7.5},
    }

    assert classify_slide_strategy(page) == "background_plus_foreground_text"


def test_classify_slide_strategy_fragmented_objects():
    page = {
        "text_box_count": 8,
        "pictures": 12,
        "shapes": 36,
        "tables": 0,
        "largest_picture_area_ratio": 0.72,
        "total_picture_area_ratio": 1.0,
        "picture_coverage_ratio": 0.89,
        "picture_geometries": [{"x": 0, "y": 1, "w": 9, "h": 5}],
        "shape_geometries": [],
        "text_box_geometries": [{"x": 1, "y": 1, "w": 4, "h": 0.5}],
        "size": {"width": 13.333, "height": 7.5},
    }

    assert classify_slide_strategy(page) == "fragmented_objects"


def test_classify_slide_strategy_mostly_editable():
    page = {
        "text_box_count": 6,
        "pictures": 1,
        "shapes": 4,
        "tables": 0,
        "largest_picture_area_ratio": 0.1,
        "total_picture_area_ratio": 0.1,
        "picture_coverage_ratio": 0.1,
        "picture_geometries": [{"x": 0, "y": 0, "w": 1, "h": 1}],
        "shape_geometries": [],
        "text_box_geometries": [{"x": 1, "y": 1, "w": 4, "h": 0.5}],
        "size": {"width": 13.333, "height": 7.5},
    }

    assert classify_slide_strategy(page) == "mostly_editable"


def test_profile_pptx_strategy_from_inspection_counts_strategies():
    inspection = {
        "pages": [
            {
                "slide": "ppt/slides/slide1.xml",
                "size": {"width": 13.333, "height": 7.5},
                "text_runs": 5,
                "text_box_count": 3,
                "pictures": 3,
                "shapes": 8,
                "tables": 0,
                "largest_picture_area_ratio": 0.94,
                "total_picture_area_ratio": 1.0,
                "picture_coverage_ratio": 0.95,
                "picture_geometries": [{"x": 0, "y": 0, "w": 13.333, "h": 7.5}],
                "shape_geometries": [],
                "text_box_geometries": [{"x": 1, "y": 1, "w": 4, "h": 0.5}],
            },
            {
                "slide": "ppt/slides/slide2.xml",
                "size": {"width": 13.333, "height": 7.5},
                "text_runs": 0,
                "text_box_count": 0,
                "pictures": 0,
                "shapes": 0,
                "tables": 0,
                "largest_picture_area_ratio": 0,
                "total_picture_area_ratio": 0,
                "picture_coverage_ratio": 0,
                "picture_geometries": [],
                "shape_geometries": [],
                "text_box_geometries": [],
            },
        ]
    }

    profile = profile_pptx_strategy_from_inspection(inspection)

    assert profile["strategy_counts"] == {
        "background_plus_foreground_text": 1,
        "fragmented_objects": 0,
        "mostly_editable": 0,
        "unknown": 1,
    }
    assert profile["pages"][0]["page_number"] == 1
    assert profile["pages"][0]["strategy"] == "background_plus_foreground_text"
