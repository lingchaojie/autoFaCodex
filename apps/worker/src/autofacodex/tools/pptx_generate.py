from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt

from autofacodex.contracts import SlideModel


def generate_pptx(model: SlideModel, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    presentation = Presentation()
    if model.slides:
        presentation.slide_width = Inches(model.slides[0].size.width)
        presentation.slide_height = Inches(model.slides[0].size.height)

    blank_layout = presentation.slide_layouts[6]
    for slide_spec in model.slides:
        slide = presentation.slides.add_slide(blank_layout)
        for element in slide_spec.elements:
            if element.type == "text":
                box = slide.shapes.add_textbox(
                    Inches(element.x),
                    Inches(element.y),
                    Inches(element.w),
                    Inches(element.h),
                )
                paragraph = box.text_frame.paragraphs[0]
                run = paragraph.add_run()
                run.text = element.text or ""
                font_size = element.style.get("font_size", 18)
                run.font.size = Pt(font_size)
    presentation.save(output_path)
    return output_path
