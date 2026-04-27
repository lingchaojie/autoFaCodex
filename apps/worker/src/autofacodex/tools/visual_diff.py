from pathlib import Path

import numpy as np
from PIL import Image, ImageChops
from skimage.metrics import structural_similarity


def write_diff_image(reference: Path, candidate: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(reference) as ref_image, Image.open(candidate) as cand_image:
        ref = ref_image.convert("RGB")
        cand = cand_image.convert("RGB").resize(ref.size)
        ImageChops.difference(ref, cand).save(output_path)
    return output_path


def write_compare_image(reference: Path, candidate: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(reference) as ref_image, Image.open(candidate) as cand_image:
        ref = ref_image.convert("RGB")
        cand = cand_image.convert("RGB").resize(ref.size)
        combined = Image.new("RGB", (ref.width + cand.width, ref.height), "white")
        combined.paste(ref, (0, 0))
        combined.paste(cand, (ref.width, 0))
        combined.save(output_path)
    return output_path


def compare_images(reference: Path, candidate: Path) -> float:
    with Image.open(reference) as ref_image, Image.open(candidate) as cand_image:
        ref = ref_image.convert("L")
        cand = cand_image.convert("L").resize(ref.size)
        ref_array = np.asarray(ref)
        cand_array = np.asarray(cand)

    min_side = min(ref_array.shape)
    if min_side < 3:
        pixel_delta = np.abs(ref_array.astype(float) - cand_array.astype(float)).mean()
        score = 1.0 - (pixel_delta / 255.0)
        return float(max(0.0, min(1.0, score)))

    win_size = min(7, min_side)
    if win_size % 2 == 0:
        win_size -= 1
    score, _ = structural_similarity(
        ref_array,
        cand_array,
        full=True,
        win_size=win_size,
    )
    return float(max(0.0, min(1.0, score)))
