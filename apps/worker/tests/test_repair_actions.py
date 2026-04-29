from autofacodex.tools.repair_actions import apply_repair_action


def _model():
    return {
        "slides": [
            {
                "page_number": 1,
                "size": {"width": 10, "height": 7.5},
                "elements": [
                    {
                        "id": "image-1",
                        "type": "image",
                        "x": 2.0,
                        "y": 2.0,
                        "w": 2.0,
                        "h": 1.0,
                        "style": {},
                    },
                    {
                        "id": "title",
                        "type": "text",
                        "x": 1.0,
                        "y": 1.0,
                        "w": 3.0,
                        "h": 0.5,
                        "text": "Title",
                        "style": {},
                    },
                ],
                "raster_fallback_regions": [],
            }
        ]
    }


def test_apply_repair_action_marks_region_images_as_background():
    model = _model()
    result = apply_repair_action(
        model,
        page_number=1,
        action={
            "action": "mark_region_background",
            "region": [0.1, 0.1, 0.5, 0.5],
            "min_overlap_ratio": 0.2,
        },
    )

    assert result["changed_element_ids"] == ["image-1"]
    image = model["slides"][0]["elements"][0]
    assert image["style"]["role"] == "background"


def test_apply_repair_action_noops_unknown_action():
    model = _model()
    result = apply_repair_action(
        model,
        page_number=1,
        action={"action": "unsupported_action", "region": [0, 0, 1, 1]},
    )

    assert result["changed_element_ids"] == []
    assert result["status"] == "noop"
