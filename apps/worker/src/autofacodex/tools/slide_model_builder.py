from autofacodex.contracts import SlideElement, SlideModel, SlideSize, SlideSpec


def build_initial_slide_model(extracted: dict) -> SlideModel:
    slides: list[SlideSpec] = []
    for page in extracted["pages"]:
        width = 13.333
        height = 13.333 * float(page["height"]) / float(page["width"])
        elements: list[SlideElement] = []
        text = page.get("text", "").strip()
        if text:
            elements.append(
                SlideElement(
                    id=f"p{page['page_number']}-text-1",
                    type="text",
                    text=text,
                    x=0.5,
                    y=0.5,
                    w=width - 1,
                    h=max(1.0, height - 1),
                    style={"font_size": 14},
                )
            )
        slides.append(
            SlideSpec(
                page_number=page["page_number"],
                size=SlideSize(width=width, height=height),
                elements=elements,
                raster_fallback_regions=[],
            )
        )
    return SlideModel(slides=slides)
