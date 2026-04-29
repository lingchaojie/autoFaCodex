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


def extract_diff_regions(
    source_path: Path,
    candidate_path: Path,
    *,
    threshold: float = 0.1,
    min_area_ratio: float = 0.01,
    max_regions: int = 5,
) -> list[dict]:
    with Image.open(source_path) as source_image, Image.open(candidate_path) as candidate_image:
        source = source_image.convert("RGB")
        candidate = candidate_image.convert("RGB").resize(source.size)

    diff = ImageChops.difference(source, candidate).convert("L")
    width, height = diff.size
    pixels = diff.load()
    cutoff = int(max(0.0, min(1.0, threshold)) * 255)
    visited: set[tuple[int, int]] = set()
    regions: list[dict] = []

    for y in range(height):
        for x in range(width):
            if (x, y) in visited or pixels[x, y] <= cutoff:
                continue
            stack = [(x, y)]
            visited.add((x, y))
            xs: list[int] = []
            ys: list[int] = []
            while stack:
                cx, cy = stack.pop()
                xs.append(cx)
                ys.append(cy)
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    if (nx, ny) in visited or pixels[nx, ny] <= cutoff:
                        continue
                    visited.add((nx, ny))
                    stack.append((nx, ny))

            area_ratio = len(xs) / float(width * height)
            if area_ratio < min_area_ratio:
                continue
            min_x, max_x = min(xs), max(xs) + 1
            min_y, max_y = min(ys), max(ys) + 1
            regions.append(
                {
                    "region": [
                        round(min_x / width, 4),
                        round(min_y / height, 4),
                        round(max_x / width, 4),
                        round(max_y / height, 4),
                    ],
                    "area_ratio": round(area_ratio, 6),
                }
            )

    return sorted(regions, key=lambda item: item["area_ratio"], reverse=True)[:max_regions]


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
