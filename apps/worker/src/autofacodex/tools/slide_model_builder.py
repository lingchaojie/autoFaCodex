from autofacodex.contracts import SlideElement, SlideModel, SlideSize, SlideSpec

DECK_WIDTH = 13.333


def _positive_float(page: dict, field: str) -> float:
    try:
        value = page[field]
    except KeyError as exc:
        raise ValueError(f"Page {page.get('page_number', '?')} is missing {field}") from exc

    try:
        dimension = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Page {page.get('page_number', '?')} {field} must be numeric and greater than 0"
        ) from exc

    if dimension <= 0:
        raise ValueError(
            f"Page {page.get('page_number', '?')} {field} must be numeric and greater than 0"
        )
    return dimension


def build_initial_slide_model(extracted: dict) -> SlideModel:
    slides: list[SlideSpec] = []
    pages = extracted["pages"]
    page_dimensions = [
        (_positive_float(page, "width"), _positive_float(page, "height")) for page in pages
    ]
    if not pages:
        return SlideModel(slides=slides)

    first_width, first_height = page_dimensions[0]
    deck_size = SlideSize(width=DECK_WIDTH, height=DECK_WIDTH * first_height / first_width)

    for page in pages:
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
                    w=deck_size.width - 1,
                    h=max(1.0, deck_size.height - 1),
                    style={"font_size": 14},
                )
            )
        slides.append(
            SlideSpec(
                page_number=page["page_number"],
                size=deck_size,
                elements=elements,
                raster_fallback_regions=[],
            )
        )
    return SlideModel(slides=slides)
