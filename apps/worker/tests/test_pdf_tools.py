import hashlib
import json
import math
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from autofacodex.tools import pdf_extract
from autofacodex.tools.pdf_extract import extract_pdf
from autofacodex.tools.pdf_render import render_pdf_pages


def make_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(400, 300))
    c.setFont("Helvetica", 24)
    c.drawString(72, 220, "Editable Title")
    c.rect(70, 120, 160, 60, stroke=1, fill=0)
    c.save()


def make_pdf_with_image(path: Path, image_path: Path) -> None:
    image = Image.new("RGB", (12, 10), color=(220, 20, 60))
    image.save(image_path)

    c = canvas.Canvas(str(path), pagesize=(400, 300))
    c.drawImage(ImageReader(str(image_path)), 80, 140, width=120, height=100)
    c.save()


def image_bytes(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (12, 10), color=color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def mask_bytes(alpha: int) -> bytes:
    image = Image.new("L", (12, 10), color=alpha)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def corner_image_bytes() -> bytes:
    image = Image.new("RGB", (2, 2), color=(0, 0, 0))
    image.putpixel((0, 0), (255, 0, 0))
    image.putpixel((1, 0), (0, 255, 0))
    image.putpixel((0, 1), (0, 0, 255))
    image.putpixel((1, 1), (255, 255, 0))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_extract_pdf_text_and_page_size(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf)

    result = extract_pdf(pdf, tmp_path / "extracted")

    page = result["pages"][0]
    assert page["page_number"] == 1
    assert page["width"] == 400
    assert page["height"] == 300
    assert page["drawing_count"] >= 1
    assert "Editable Title" in page["text"]


def test_extract_pdf_writes_pages_json_matching_result(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    output_dir = tmp_path / "extracted"
    make_pdf(pdf)

    result = extract_pdf(pdf, output_dir)

    pages_json = output_dir / "pages.json"
    assert pages_json.is_file()
    assert json.loads(pages_json.read_text(encoding="utf-8")) == result


def test_extract_pdf_with_image_writes_json_serializable_metadata(tmp_path: Path):
    pdf = tmp_path / "image.pdf"
    output_dir = tmp_path / "extracted"
    make_pdf_with_image(pdf, tmp_path / "sample.png")

    result = extract_pdf(pdf, output_dir)

    assert result["pages"][0]["image_count"] >= 1
    pages_json = output_dir / "pages.json"
    saved = json.loads(pages_json.read_text(encoding="utf-8"))
    assert saved == result
    image_blocks = [
        block
        for block in result["pages"][0]["text_blocks"]
        if block["type"] == "image"
    ]
    assert image_blocks
    assert all("image" not in block for block in image_blocks)
    assert all(block["source"].startswith("objects/images/") for block in image_blocks)
    assert all((output_dir / block["source"]).is_file() for block in image_blocks)
    assert all(block["content_hash"] for block in image_blocks)


def test_extract_pdf_prefers_image_block_bytes_over_ambiguous_xrefs(tmp_path: Path):
    block_bytes = image_bytes((20, 140, 220))
    wrong_xref_bytes = image_bytes((220, 20, 60))
    fake_doc = SimpleNamespace(
        extract_image=lambda _xref: {"image": wrong_xref_bytes, "ext": "png"}
    )

    block = {
        "type": 1,
        "bbox": [10, 20, 110, 120],
        "width": 12,
        "height": 10,
        "ext": "png",
        "image": block_bytes,
    }

    image_xrefs = [99]

    metadata = pdf_extract._image_block_metadata(
        fake_doc,
        tmp_path / "extracted",
        1,
        1,
        block,
        image_xrefs,
        [],
    )

    extracted_image = Image.open(tmp_path / "extracted" / metadata["source"]).convert("RGB")
    assert extracted_image.getpixel((0, 0)) == (20, 140, 220)
    assert metadata["content_hash"] == hashlib.sha256(
        (tmp_path / "extracted" / metadata["source"]).read_bytes()
    ).hexdigest()
    assert "xref" not in metadata
    assert image_xrefs == [99]


def test_extract_pdf_applies_image_block_mask_as_alpha(tmp_path: Path):
    fake_doc = SimpleNamespace(
        extract_image=lambda _xref: pytest.fail("block bytes should not need xref")
    )
    block = {
        "type": 1,
        "bbox": [10, 20, 110, 120],
        "width": 12,
        "height": 10,
        "ext": "png",
        "image": image_bytes((20, 140, 220)),
        "mask": mask_bytes(64),
    }

    metadata = pdf_extract._image_block_metadata(
        fake_doc,
        tmp_path / "extracted",
        1,
        1,
        block,
        [],
        [],
    )

    assert metadata["source"].endswith(".png")
    extracted_image = Image.open(tmp_path / "extracted" / metadata["source"]).convert("RGBA")
    assert extracted_image.getpixel((0, 0)) == (20, 140, 220, 64)


def test_image_mask_alpha_is_calibrated_against_pdf_rendered_crop():
    base = image_bytes((20, 20, 20))
    mask = mask_bytes(128)
    reference_crop = Image.new("RGB", (12, 10), color=(248, 248, 248))

    masked, ext = pdf_extract._apply_image_mask(base, mask, reference_crop)

    assert ext == "png"
    alpha = Image.open(BytesIO(masked)).convert("RGBA").getpixel((0, 0))[3]
    assert 0 < alpha < 16


def test_write_image_asset_uses_rendered_crop_when_raw_bytes_do_not_match_pdf_display(
    tmp_path: Path,
):
    fake_doc = SimpleNamespace(
        extract_image=lambda _xref: pytest.fail("block bytes should not need xref")
    )
    reference_crop = Image.new("RGB", (12, 10), color=(248, 248, 248))

    source = pdf_extract._write_image_asset(
        fake_doc,
        tmp_path / "extracted",
        1,
        1,
        None,
        "png",
        image_bytes((20, 20, 20)),
        reference_crop=reference_crop,
    )

    extracted_image = Image.open(tmp_path / "extracted" / source).convert("RGB")
    assert extracted_image.getpixel((0, 0)) == (248, 248, 248)


def test_render_reference_crop_returns_none_when_pdf_renderer_rejects_clip():
    class BadPixmap:
        def tobytes(self, _format: str):
            raise RuntimeError("Invalid bandwriter header dimensions/setup")

    class FakePage:
        rect = fitz.Rect(0, 0, 100, 100)

        def get_pixmap(self, **_kwargs):
            return BadPixmap()

    assert pdf_extract._render_reference_crop(FakePage(), [0, 0, 100, 100]) is None


def test_extract_pdf_includes_simple_rectangle_drawings(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf)

    result = extract_pdf(pdf, tmp_path / "extracted")

    drawings = result["pages"][0]["drawings"]
    assert any(drawing["shape"] == "rect" for drawing in drawings)
    rect = next(drawing for drawing in drawings if drawing["shape"] == "rect")
    assert rect["bbox"] == pytest.approx([70, 120, 230, 180])
    assert rect["stroke_width"] > 0


def test_drawing_metadata_preserves_rect_opacity():
    metadata = pdf_extract._drawing_metadata(
        {
            "items": [("re", fitz.Rect(0, 0, 10, 10), 1)],
            "color": [0, 0, 0],
            "fill": [0, 0, 0],
            "width": 1,
            "fill_opacity": 0.36863,
            "stroke_opacity": 0.5,
            "seqno": 8,
        }
    )

    assert metadata["fill_opacity"] == pytest.approx(0.36863)
    assert metadata["stroke_opacity"] == pytest.approx(0.5)


def test_extract_pdf_includes_paint_order_for_editable_elements(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf)

    result = extract_pdf(pdf, tmp_path / "extracted")

    page = result["pages"][0]
    text_spans = [
        span
        for block in page["text_blocks"]
        if block["type"] == "text"
        for line in block["lines"]
        for span in line["spans"]
        if span["text"].strip()
    ]
    assert all(isinstance(span["seqno"], int) for span in text_spans)
    assert all(isinstance(drawing["seqno"], int) for drawing in page["drawings"])


def test_image_block_metadata_prefers_larger_bboxlog_image_bbox(tmp_path: Path):
    fake_doc = SimpleNamespace()
    block = {
        "type": "image",
        "bbox": [531, 0, 960, 540],
        "image": image_bytes((20, 20, 20)),
        "ext": "png",
        "width": 429,
        "height": 540,
    }

    metadata = pdf_extract._image_block_metadata(
        fake_doc,
        tmp_path / "extracted",
        1,
        1,
        block,
        [],
        [("fill-image", (0, 0, 960, 540))],
        page=None,
    )

    assert metadata["bbox"] == [0.0, 0.0, 960.0, 540.0]


def test_image_block_metadata_does_not_expand_small_icon_to_full_page(tmp_path: Path):
    fake_doc = SimpleNamespace()
    block = {
        "type": "image",
        "bbox": [867, 21, 935, 34],
        "image": image_bytes((20, 20, 20)),
        "ext": "png",
        "width": 68,
        "height": 13,
    }

    metadata = pdf_extract._image_block_metadata(
        fake_doc,
        tmp_path / "extracted",
        1,
        1,
        block,
        [],
        [("fill-image", (0, 0, 960, 540))],
        page=None,
    )

    assert metadata["bbox"] == [867.0, 21.0, 935.0, 34.0]


def test_missing_image_info_blocks_adds_unrepresented_image(tmp_path: Path):
    class FakeDoc:
        def extract_image(self, xref: int):
            assert xref == 42
            return {"image": image_bytes((10, 20, 30)), "ext": "png"}

    blocks = pdf_extract._missing_image_info_blocks(
        FakeDoc(),
        tmp_path / "extracted",
        1,
        next_image_number=2,
        image_infos=[
            {
                "xref": 42,
                "bbox": (0, 0, 960, 540),
                "width": 960,
                "height": 540,
                "colorspace": 3,
            }
        ],
        existing_image_blocks=[
            {"type": "image", "bbox": [867, 21, 935, 34]},
        ],
        bboxlog=[("fill-image", (0, 0, 960, 540))],
        page=None,
    )

    assert len(blocks) == 1
    assert blocks[0]["bbox"] == [0.0, 0.0, 960.0, 540.0]
    assert blocks[0]["xref"] == 42
    assert blocks[0]["source"] == "objects/images/page-001-image-002.png"


def test_missing_image_info_blocks_skips_represented_image(tmp_path: Path):
    blocks = pdf_extract._missing_image_info_blocks(
        SimpleNamespace(),
        tmp_path / "extracted",
        1,
        next_image_number=2,
        image_infos=[
            {
                "xref": 42,
                "bbox": (0, 0, 960, 540),
                "width": 960,
                "height": 540,
            }
        ],
        existing_image_blocks=[
            {"type": "image", "bbox": [0, 0, 960, 540]},
        ],
        bboxlog=[("fill-image", (0, 0, 960, 540))],
        page=None,
    )

    assert blocks == []


def test_extract_pdf_adds_image_info_missing_from_text_dict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    class FakePage:
        rect = SimpleNamespace(width=960, height=540)

        def get_text(self, option: str):
            if option == "dict":
                return {"blocks": []}
            if option == "text":
                return ""
            raise AssertionError(option)

        def get_texttrace(self):
            return []

        def get_images(self, full: bool = False):
            return []

        def get_drawings(self):
            return []

        def get_bboxlog(self):
            return [("fill-image", (0, 0, 960, 540))]

        def get_image_info(self, xrefs: bool = False):
            return [
                {
                    "xref": 42,
                    "bbox": (0, 0, 960, 540),
                    "width": 960,
                    "height": 540,
                    "colorspace": 3,
                }
            ]

    class FakeDoc:
        def __iter__(self):
            return iter([FakePage()])

        def extract_image(self, xref: int):
            assert xref == 42
            return {"image": image_bytes((10, 20, 30)), "ext": "png"}

        def close(self):
            pass

    monkeypatch.setattr(pdf_extract.fitz, "open", lambda _path: FakeDoc())
    monkeypatch.setattr(pdf_extract, "_render_reference_crop", lambda *_args: None)

    result = extract_pdf(tmp_path / "sample.pdf", tmp_path / "extracted")

    image_blocks = [
        block
        for block in result["pages"][0]["text_blocks"]
        if block["type"] == "image"
    ]
    assert len(image_blocks) == 1
    assert image_blocks[0]["bbox"] == [0.0, 0.0, 960.0, 540.0]
    assert image_blocks[0]["xref"] == 42
    assert (tmp_path / "extracted" / image_blocks[0]["source"]).is_file()


def test_image_info_block_uses_transformed_raw_image_instead_of_page_crop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    class FakeDoc:
        def extract_image(self, xref: int):
            assert xref == 42
            return {"image": corner_image_bytes(), "ext": "png"}

    monkeypatch.setattr(
        pdf_extract,
        "_render_reference_crop",
        lambda *_args: Image.new("RGB", (2, 2), color=(10, 20, 30)),
    )

    metadata = pdf_extract._image_block_metadata(
        FakeDoc(),
        tmp_path / "extracted",
        1,
        1,
        pdf_extract._image_info_block(
            {
                "xref": 42,
                "bbox": (0, 0, 2, 2),
                "transform": (-2, 0, 0, -2, 2, 2),
            }
        ),
        [],
        [("fill-image", (0, 0, 2, 2))],
        page=object(),
    )

    extracted = Image.open(tmp_path / "extracted" / metadata["source"]).convert("RGB")
    assert extracted.getpixel((0, 0)) == (255, 255, 0)


def test_image_info_block_can_use_page_crop_for_foreground_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    class FakeDoc:
        def extract_image(self, xref: int):
            assert xref == 42
            return {"image": corner_image_bytes(), "ext": "png"}

    monkeypatch.setattr(
        pdf_extract,
        "_render_reference_crop",
        lambda *_args: Image.new("RGB", (2, 2), color=(10, 20, 30)),
    )

    metadata = pdf_extract._image_block_metadata(
        FakeDoc(),
        tmp_path / "extracted",
        1,
        1,
        pdf_extract._image_info_block(
            {
                "xref": 42,
                "bbox": (0, 0, 2, 2),
                "transform": (-2, 0, 0, -2, 2, 2),
            },
            allow_reference_crop=True,
        ),
        [],
        [("fill-image", (0, 0, 2, 2))],
        page=object(),
    )

    extracted = Image.open(tmp_path / "extracted" / metadata["source"]).convert("RGB")
    assert extracted.getpixel((0, 0)) == (10, 20, 30)


def test_render_pdf_pages_outputs_png(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf)

    renders = render_pdf_pages(pdf, tmp_path / "renders")

    assert len(renders) == 1
    assert renders[0].suffix == ".png"
    assert renders[0].is_file()


def test_render_pdf_pages_output_dimensions_reflect_zoom(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf)

    renders = render_pdf_pages(pdf, tmp_path / "renders", zoom=1.5)

    pixmap = fitz.Pixmap(renders[0])
    assert pixmap.width == 600
    assert pixmap.height == 450


@pytest.mark.parametrize("zoom", [0, -1, math.nan, 8.1])
def test_render_pdf_pages_rejects_invalid_zoom_before_creating_output(
    tmp_path: Path, zoom: float
):
    pdf = tmp_path / "sample.pdf"
    output_dir = tmp_path / "renders"
    make_pdf(pdf)

    with pytest.raises(ValueError, match="zoom"):
        render_pdf_pages(pdf, output_dir, zoom=zoom)

    assert not output_dir.exists()
