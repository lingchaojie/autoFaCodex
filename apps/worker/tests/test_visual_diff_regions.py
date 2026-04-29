from pathlib import Path

from PIL import Image, ImageDraw

from autofacodex.tools import visual_diff


def test_extract_diff_regions_returns_normalized_bounding_boxes(tmp_path: Path):
    source = tmp_path / "source.png"
    candidate = tmp_path / "candidate.png"
    Image.new("RGB", (100, 100), "white").save(source)
    changed = Image.new("RGB", (100, 100), "white")
    draw = ImageDraw.Draw(changed)
    draw.rectangle([20, 30, 49, 59], fill="black")
    changed.save(candidate)

    regions = visual_diff.extract_diff_regions(
        source,
        candidate,
        threshold=0.1,
        min_area_ratio=0.01,
    )

    assert regions == [
        {
            "region": [0.2, 0.3, 0.5, 0.6],
            "area_ratio": 0.09,
        }
    ]


def test_extract_diff_regions_filters_tiny_noise(tmp_path: Path):
    source = tmp_path / "source.png"
    candidate = tmp_path / "candidate.png"
    Image.new("RGB", (100, 100), "white").save(source)
    changed = Image.new("RGB", (100, 100), "white")
    changed.putpixel((1, 1), (0, 0, 0))
    changed.save(candidate)

    assert visual_diff.extract_diff_regions(source, candidate, threshold=0.1, min_area_ratio=0.01) == []
