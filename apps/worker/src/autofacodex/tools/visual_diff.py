from pathlib import Path

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity


def compare_images(reference: Path, candidate: Path) -> float:
    ref = Image.open(reference).convert("L")
    cand = Image.open(candidate).convert("L").resize(ref.size)
    ref_array = np.asarray(ref)
    cand_array = np.asarray(cand)
    score, _ = structural_similarity(ref_array, cand_array, full=True)
    return float(max(0.0, min(1.0, score)))
