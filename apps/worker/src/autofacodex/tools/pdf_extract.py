import hashlib
import json
from io import BytesIO
from pathlib import Path

import fitz
import numpy as np
from PIL import Image, UnidentifiedImageError


def _bbox(value: object) -> list[float]:
    return [float(item) for item in value or []]


def _point(value: object) -> list[float]:
    return [float(item) for item in value or []]


def _color(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return f"#{value & 0xFFFFFF:06X}"
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        channels = [max(0, min(255, round(float(item) * 255))) for item in value[:3]]
        return f"#{channels[0]:02X}{channels[1]:02X}{channels[2]:02X}"
    if isinstance(value, str):
        return value
    return None


def _overlap_area(a: list[float], b: list[float]) -> float:
    if len(a) != 4 or len(b) != 4:
        return 0.0
    left = max(a[0], b[0])
    top = max(a[1], b[1])
    right = min(a[2], b[2])
    bottom = min(a[3], b[3])
    if right <= left or bottom <= top:
        return 0.0
    return (right - left) * (bottom - top)


def _trace_text(trace: dict) -> str:
    chars = trace.get("chars", [])
    return "".join(chr(char[0]) for char in chars if char and char[0] >= 0)


def _text_traces(page: fitz.Page) -> list[dict]:
    traces = []
    for trace in page.get_texttrace():
        text = _trace_text(trace)
        if not text.strip():
            continue
        traces.append(
            {
                "text": text,
                "bbox": _bbox(trace.get("bbox")),
                "font": trace.get("font"),
                "size": trace.get("size"),
                "seqno": trace.get("seqno"),
            }
        )
    return traces


def _span_seqno(span_metadata: dict, traces: list[dict]) -> int | None:
    span_text = str(span_metadata.get("text") or "").strip()
    span_bbox = _bbox(span_metadata.get("bbox"))
    if not span_text or len(span_bbox) != 4:
        return None

    best_trace: dict | None = None
    best_overlap = 0.0
    for trace in traces:
        trace_text = str(trace.get("text") or "").strip()
        if span_text != trace_text:
            continue
        if trace.get("font") != span_metadata.get("font"):
            continue
        if (
            trace.get("size") is not None
            and span_metadata.get("size") is not None
            and abs(float(trace["size"]) - float(span_metadata["size"])) > 0.01
        ):
            continue
        overlap = _overlap_area(span_bbox, _bbox(trace.get("bbox")))
        if overlap > best_overlap:
            best_trace = trace
            best_overlap = overlap

    if best_trace is None:
        return None
    try:
        return int(best_trace["seqno"])
    except (TypeError, ValueError):
        return None


def _span_metadata(span: dict, traces: list[dict]) -> dict:
    metadata = {
        "text": span.get("text", ""),
        "bbox": _bbox(span.get("bbox")),
        "origin": _point(span.get("origin")),
        "font": span.get("font"),
        "size": span.get("size"),
        "flags": span.get("flags"),
        "color": span.get("color"),
    }
    if (seqno := _span_seqno(metadata, traces)) is not None:
        metadata["seqno"] = seqno
    return metadata


def _write_image_asset(
    doc: fitz.Document,
    output_dir: Path,
    page_number: int,
    image_number: int,
    xref: int | None,
    fallback_ext: str | None,
    image_bytes: bytes | None = None,
    mask_bytes: bytes | None = None,
    reference_crop: Image.Image | None = None,
    transform: object = None,
    allow_reference_crop: bool = True,
) -> str | None:
    image: dict | None = None
    if image_bytes is not None:
        image = {"image": image_bytes, "ext": fallback_ext or "png"}
    elif xref:
        try:
            image = doc.extract_image(int(xref))
        except (ValueError, RuntimeError):
            image = None

    if image is None:
        return None

    ext = image.get("ext") or fallback_ext or "bin"
    image_payload, ext = _apply_axis_aligned_image_transform(
        image["image"], ext, transform
    )
    image_payload, ext = _prepare_display_image_payload(
        image_payload, ext, mask_bytes, reference_crop, allow_reference_crop
    )
    source = f"objects/images/page-{page_number:03d}-image-{image_number:03d}.{ext}"
    image_path = output_dir / source
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(image_payload)
    return source


def _image_content_hash(output_dir: Path, source: str | None) -> str | None:
    if not source:
        return None
    image_path = output_dir / source
    if not image_path.is_file():
        return None
    return hashlib.sha256(image_path.read_bytes()).hexdigest()


def _prepare_display_image_payload(
    image_payload: bytes,
    ext: str,
    mask_bytes: bytes | None,
    reference_crop: Image.Image | None,
    allow_reference_crop: bool = True,
) -> tuple[bytes, str]:
    if mask_bytes is not None:
        masked = _apply_image_mask(image_payload, mask_bytes, reference_crop)
        if masked is not None:
            image_payload, ext = masked
    if (
        allow_reference_crop
        and reference_crop is not None
        and _image_visual_delta(image_payload, reference_crop) > 18
    ):
        output = BytesIO()
        reference_crop.save(output, format="PNG")
        return (output.getvalue(), "png")
    return (image_payload, ext)


def _image_save_format(ext: str) -> tuple[str, str]:
    normalized = ext.lower().lstrip(".")
    if normalized in {"jpg", "jpeg"}:
        return ("JPEG", "jpg")
    if normalized == "png":
        return ("PNG", "png")
    return ("PNG", "png")


def _axis_aligned_transform(value: object) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 6:
        return None
    try:
        a, b, c, d = (float(value[index]) for index in range(4))
    except (TypeError, ValueError):
        return None
    if abs(b) > 0.001 or abs(c) > 0.001:
        return None
    return (a, d)


def _apply_axis_aligned_image_transform(
    image_payload: bytes, ext: str, transform: object
) -> tuple[bytes, str]:
    scale = _axis_aligned_transform(transform)
    if scale is None:
        return (image_payload, ext)
    horizontal_scale, vertical_scale = scale
    if horizontal_scale >= 0 and vertical_scale >= 0:
        return (image_payload, ext)
    try:
        image = Image.open(BytesIO(image_payload))
    except (UnidentifiedImageError, OSError):
        return (image_payload, ext)
    if horizontal_scale < 0:
        image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if vertical_scale < 0:
        image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    save_format, normalized_ext = _image_save_format(ext)
    if save_format == "JPEG" and image.mode in {"RGBA", "LA", "P"}:
        image = image.convert("RGB")
    output = BytesIO()
    image.save(output, format=save_format)
    return (output.getvalue(), normalized_ext)


def _image_visual_delta(image_payload: bytes, reference_crop: Image.Image) -> float:
    try:
        image = Image.open(BytesIO(image_payload)).convert("RGBA")
    except (UnidentifiedImageError, OSError):
        return 0.0
    reference = reference_crop.convert("RGB")
    if image.size != reference.size:
        image = image.resize(reference.size)
    preview = Image.new("RGBA", reference.size, (255, 255, 255, 255))
    preview.alpha_composite(image)
    preview_array = np.asarray(preview.convert("RGB"), dtype=float)
    reference_array = np.asarray(reference, dtype=float)
    return float(np.mean(np.abs(preview_array - reference_array)))


def _apply_image_mask(
    image_payload: bytes,
    mask_payload: bytes,
    reference_crop: Image.Image | None = None,
) -> tuple[bytes, str] | None:
    try:
        base = Image.open(BytesIO(image_payload)).convert("RGBA")
        mask = Image.open(BytesIO(mask_payload)).convert("L")
    except (UnidentifiedImageError, OSError):
        return None

    if mask.size != base.size:
        mask = mask.resize(base.size)
    if reference_crop is not None:
        mask = _calibrate_mask_alpha(base, mask, reference_crop)
    base.putalpha(mask)
    output = BytesIO()
    base.save(output, format="PNG")
    return (output.getvalue(), "png")


def _calibrate_mask_alpha(
    base: Image.Image, mask: Image.Image, reference_crop: Image.Image
) -> Image.Image:
    reference = reference_crop.convert("RGB")
    if reference.size != base.size:
        sample_base = base.convert("RGB").resize(reference.size)
        sample_mask = mask.resize(reference.size)
    else:
        sample_base = base.convert("RGB")
        sample_mask = mask

    base_array = np.asarray(sample_base, dtype=float)
    mask_array = np.asarray(sample_mask, dtype=float) / 255.0
    reference_array = np.asarray(reference, dtype=float)
    alpha_effect = mask_array[..., None] * (255.0 - base_array)
    target_effect = 255.0 - reference_array
    denominator = float(np.sum(alpha_effect * alpha_effect))
    if denominator <= 0:
        return mask
    scale = float(np.sum(target_effect * alpha_effect) / denominator)
    scale = max(0.0, min(1.0, scale))
    if scale >= 0.995:
        return mask
    return mask.point(lambda alpha: round(alpha * scale))


def _render_reference_crop(
    page: fitz.Page | None, bbox: list[float], max_side: int = 1600
) -> Image.Image | None:
    if page is None or len(bbox) != 4:
        return None
    rect = fitz.Rect(bbox) & page.rect
    if rect.is_empty or rect.width <= 0 or rect.height <= 0:
        return None
    zoom = min(max_side / rect.width, max_side / rect.height, 2.0)
    if zoom <= 0:
        return None
    try:
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
        return Image.open(BytesIO(pixmap.tobytes("png"))).convert("RGB")
    except Exception:
        return None


def _text_block_metadata(block: dict, traces: list[dict]) -> dict:
    return {
        "type": "text",
        "bbox": _bbox(block.get("bbox")),
        "lines": [
            {
                "bbox": _bbox(line.get("bbox")),
                "wmode": line.get("wmode"),
                "dir": _point(line.get("dir")),
                "spans": [_span_metadata(span, traces) for span in line.get("spans", [])],
            }
            for line in block.get("lines", [])
        ],
    }


def _bboxlog_seqno(kind: str, bbox: list[float], bboxlog: list[tuple]) -> int | None:
    match = _bboxlog_match(kind, bbox, bboxlog)
    return match[0] if match is not None else None


def _bboxlog_match(
    kind: str, bbox: list[float], bboxlog: list[tuple]
) -> tuple[int, list[float]] | None:
    best_index: int | None = None
    best_overlap = 0.0
    best_bbox: list[float] = []
    for index, entry in enumerate(bboxlog):
        if len(entry) < 2 or entry[0] != kind:
            continue
        entry_bbox = _bbox(entry[1])
        overlap = _overlap_area(bbox, entry_bbox)
        if overlap > best_overlap:
            best_index = index
            best_overlap = overlap
            best_bbox = entry_bbox
    if best_index is None:
        return None
    return (best_index, best_bbox)


def _area(bbox: list[float]) -> float:
    if len(bbox) != 4:
        return 0.0
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def _corrected_image_bbox(block_bbox: list[float], bboxlog_bbox: list[float]) -> list[float]:
    block_area = _area(block_bbox)
    bboxlog_area = _area(bboxlog_bbox)
    if block_area <= 0 or bboxlog_area <= 0:
        return block_bbox
    overlap = _overlap_area(block_bbox, bboxlog_bbox)
    area_ratio = block_area / bboxlog_area
    if (
        area_ratio >= 0.25
        and overlap / block_area >= 0.95
        and bboxlog_area >= block_area * 1.25
    ):
        return bboxlog_bbox
    return block_bbox


def _bbox_close(a: list[float], b: list[float], tolerance: float = 1.0) -> bool:
    return len(a) == 4 and len(b) == 4 and all(abs(a[index] - b[index]) <= tolerance for index in range(4))


def _bbox_covers_page(
    bbox: list[float], page: fitz.Page | None, threshold: float = 0.9
) -> bool:
    if page is None or len(bbox) != 4:
        return False
    page_area = float(page.rect.width) * float(page.rect.height)
    if page_area <= 0:
        return False
    return _area(bbox) / page_area >= threshold


def _image_info_block(info: dict, allow_reference_crop: bool = False) -> dict:
    return {
        "type": 1,
        "bbox": _bbox(info.get("bbox")),
        "transform": _bbox(info.get("transform")),
        "allow_reference_crop": allow_reference_crop,
        "xref": info.get("xref"),
        "width": info.get("width"),
        "height": info.get("height"),
        "colorspace": info.get("colorspace"),
        "xres": info.get("xres"),
        "yres": info.get("yres"),
        "bpc": info.get("bpc"),
    }


def _missing_image_info_blocks(
    doc: fitz.Document,
    output_dir: Path,
    page_number: int,
    *,
    next_image_number: int,
    image_infos: list[dict],
    existing_image_blocks: list[dict],
    bboxlog: list[tuple],
    page: fitz.Page | None = None,
) -> list[dict]:
    existing_bboxes = [
        _bbox(block.get("bbox"))
        for block in existing_image_blocks
        if block.get("type") == "image"
    ]
    blocks: list[dict] = []
    image_number = next_image_number
    for info in image_infos:
        bbox = _bbox(info.get("bbox"))
        if not bbox or any(_bbox_close(bbox, existing_bbox) for existing_bbox in existing_bboxes):
            continue
        metadata = _image_block_metadata(
            doc,
            output_dir,
            page_number,
            image_number,
            _image_info_block(
                info,
                allow_reference_crop=not _bbox_covers_page(bbox, page),
            ),
            [],
            bboxlog,
            page,
        )
        blocks.append(metadata)
        existing_bboxes.append(_bbox(metadata.get("bbox")))
        image_number += 1
    return blocks


def _image_block_metadata(
    doc: fitz.Document,
    output_dir: Path,
    page_number: int,
    image_number: int,
    block: dict,
    image_xrefs: list[int],
    bboxlog: list[tuple],
    page: fitz.Page | None = None,
) -> dict:
    block_xref = block.get("xref")
    image_bytes = block.get("image")
    xref = block_xref
    if xref is None and image_bytes is None and image_xrefs:
        xref = image_xrefs.pop(0)
    bbox = _bbox(block.get("bbox"))
    bboxlog_match = _bboxlog_match("fill-image", bbox, bboxlog)
    seqno = bboxlog_match[0] if bboxlog_match is not None else None
    if bboxlog_match is not None:
        bbox = _corrected_image_bbox(bbox, bboxlog_match[1])
    source = _write_image_asset(
        doc,
        output_dir,
        page_number,
        image_number,
        int(xref) if xref else None,
        block.get("ext"),
        image_bytes,
        block.get("mask"),
        _render_reference_crop(page, bbox),
        block.get("transform"),
        bool(block.get("allow_reference_crop", True)),
    )
    content_hash = _image_content_hash(output_dir, source)
    metadata = {
        "type": "image",
        "bbox": bbox,
        "width": block.get("width"),
        "height": block.get("height"),
        "ext": block.get("ext"),
        "colorspace": block.get("colorspace"),
        "xres": block.get("xres"),
        "yres": block.get("yres"),
        "bpc": block.get("bpc"),
        "xref": xref,
        "source": source,
        "content_hash": content_hash,
        "seqno": seqno,
    }
    return {key: value for key, value in metadata.items() if value is not None}


def _block_metadata(
    doc: fitz.Document,
    output_dir: Path,
    page_number: int,
    image_number: int,
    block: dict,
    image_xrefs: list[int],
    traces: list[dict],
    bboxlog: list[tuple],
    page: fitz.Page | None = None,
) -> dict:
    if block.get("type") == 0:
        return _text_block_metadata(block, traces)
    if block.get("type") == 1:
        return _image_block_metadata(
            doc,
            output_dir,
            page_number,
            image_number,
            block,
            image_xrefs,
            bboxlog,
            page,
        )
    return {
        "type": block.get("type"),
        "bbox": _bbox(block.get("bbox")),
    }


def _drawing_metadata(drawing: dict) -> dict | None:
    for item in drawing.get("items", []):
        if item and item[0] == "re":
            metadata = {
                "shape": "rect",
                "bbox": _bbox(item[1]),
                "stroke": _color(drawing.get("color")),
                "fill": _color(drawing.get("fill")),
                "stroke_width": drawing.get("width"),
                "fill_opacity": drawing.get("fill_opacity"),
                "stroke_opacity": drawing.get("stroke_opacity"),
                "seqno": drawing.get("seqno"),
            }
            return {key: value for key, value in metadata.items() if value is not None}
    items = drawing.get("items", [])
    if len(items) == 1 and items[0] and items[0][0] == "l":
        metadata = {
            "shape": "line",
            "bbox": _bbox(drawing.get("rect")),
            "p1": _point(items[0][1]),
            "p2": _point(items[0][2]),
            "stroke": _color(drawing.get("color")),
            "stroke_width": drawing.get("width"),
            "stroke_opacity": drawing.get("stroke_opacity"),
            "seqno": drawing.get("seqno"),
        }
        return {key: value for key, value in metadata.items() if value is not None}
    return None


def extract_pdf(pdf_path: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    try:
        pages = []
        for index, page in enumerate(doc, start=1):
            text_dict = page.get_text("dict")
            traces = _text_traces(page)
            images = page.get_images(full=True)
            image_xrefs = [image[0] for image in images]
            drawings = page.get_drawings()
            bboxlog = page.get_bboxlog()
            text_blocks = []
            image_number = 0
            for block in text_dict.get("blocks", []):
                if block.get("type") == 1:
                    image_number += 1
                text_blocks.append(
                    _block_metadata(
                        doc,
                        output_dir,
                        index,
                        image_number,
                        block,
                        image_xrefs,
                        traces,
                        bboxlog,
                        page,
                    )
                )
            try:
                image_infos = page.get_image_info(xrefs=True)
            except (AttributeError, RuntimeError, ValueError):
                image_infos = []
            text_blocks.extend(
                _missing_image_info_blocks(
                    doc,
                    output_dir,
                    index,
                    next_image_number=image_number + 1,
                    image_infos=image_infos,
                    existing_image_blocks=[
                        block
                        for block in text_blocks
                        if block.get("type") == "image"
                    ],
                    bboxlog=bboxlog,
                    page=page,
                )
            )
            drawing_metadata = [
                metadata
                for drawing in drawings
                if (metadata := _drawing_metadata(drawing)) is not None
            ]
            pages.append(
                {
                    "page_number": index,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "text": page.get_text("text"),
                    "text_blocks": text_blocks,
                    "image_count": len(images),
                    "drawing_count": len(drawings),
                    "drawings": drawing_metadata,
                }
            )
        result = {"pages": pages}
        (output_dir / "pages.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        return result
    finally:
        doc.close()
