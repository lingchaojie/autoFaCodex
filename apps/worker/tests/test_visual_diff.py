from pathlib import Path

from PIL import Image

from autofacodex.tools.visual_diff import (
    compare_images,
    write_compare_image,
    write_diff_image,
)


def test_write_diff_image_creates_png(tmp_path: Path):
    reference = tmp_path / "reference.png"
    candidate = tmp_path / "candidate.png"
    output = tmp_path / "diff.png"
    Image.new("RGB", (10, 10), color=(255, 255, 255)).save(reference)
    Image.new("RGB", (10, 10), color=(0, 0, 0)).save(candidate)

    result = write_diff_image(reference, candidate, output)

    assert result == output
    assert output.is_file()
    assert Image.open(output).size == (10, 10)


def test_write_compare_image_places_images_side_by_side(tmp_path: Path):
    reference = tmp_path / "reference.png"
    candidate = tmp_path / "candidate.png"
    output = tmp_path / "compare.png"
    Image.new("RGB", (10, 10), color=(255, 255, 255)).save(reference)
    Image.new("RGB", (10, 10), color=(0, 0, 0)).save(candidate)

    result = write_compare_image(reference, candidate, output)

    assert result == output
    assert Image.open(output).size == (20, 10)


def test_compare_images_still_scores_identical_images(tmp_path: Path):
    reference = tmp_path / "reference.png"
    candidate = tmp_path / "candidate.png"
    Image.new("RGB", (10, 10), color=(255, 255, 255)).save(reference)
    Image.new("RGB", (10, 10), color=(255, 255, 255)).save(candidate)

    assert compare_images(reference, candidate) == 1.0
