from typing import Literal

from pydantic import BaseModel, Field


class TaskManifest(BaseModel):
    task_id: str
    workflow_type: Literal["pdf_to_ppt"]
    input_pdf: str
    attempt: int = Field(ge=1)
    max_attempts: int = Field(ge=1)


class SlideSize(BaseModel):
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class SlideElement(BaseModel):
    id: str
    type: Literal["text", "image", "shape", "table", "path"]
    x: float
    y: float
    w: float = Field(ge=0)
    h: float = Field(ge=0)
    text: str | None = None
    source: str | None = None
    style: dict = Field(default_factory=dict)


class RasterFallbackRegion(BaseModel):
    x: float
    y: float
    w: float
    h: float
    reason: str


class SlideSpec(BaseModel):
    page_number: int = Field(ge=1)
    size: SlideSize
    elements: list[SlideElement] = Field(default_factory=list)
    raster_fallback_regions: list[RasterFallbackRegion] = Field(default_factory=list)


class SlideModel(BaseModel):
    slides: list[SlideSpec]


class ValidatorIssue(BaseModel):
    type: str
    message: str
    suggested_action: str
    region: list[float] | None = None


class PageValidation(BaseModel):
    page_number: int = Field(ge=1)
    status: Literal["pass", "repair_needed", "manual_review", "failed"]
    visual_score: float = Field(ge=0, le=1)
    editable_score: float = Field(ge=0, le=1)
    text_coverage_score: float = Field(ge=0, le=1)
    raster_fallback_ratio: float = Field(ge=0, le=1)
    issues: list[ValidatorIssue] = Field(default_factory=list)


class ValidatorReport(BaseModel):
    task_id: str
    attempt: int = Field(ge=1)
    pages: list[PageValidation]
