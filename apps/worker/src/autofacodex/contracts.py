from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskManifest(ContractModel):
    task_id: str
    workflow_type: Literal["pdf_to_ppt"]
    input_pdf: str
    attempt: int = Field(ge=1)
    max_attempts: int = Field(ge=1)


class SlideSize(ContractModel):
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class SlideElement(ContractModel):
    id: str
    type: Literal["text", "image", "shape", "table", "path"]
    x: float
    y: float
    w: float = Field(ge=0)
    h: float = Field(ge=0)
    text: str | None = None
    source: str | None = None
    style: dict = Field(default_factory=dict)


class RasterFallbackRegion(ContractModel):
    x: float
    y: float
    w: float = Field(gt=0)
    h: float = Field(gt=0)
    reason: str


class SlideSpec(ContractModel):
    page_number: int = Field(ge=1)
    size: SlideSize
    elements: list[SlideElement] = Field(default_factory=list)
    raster_fallback_regions: list[RasterFallbackRegion] = Field(default_factory=list)


class SlideModel(ContractModel):
    slides: list[SlideSpec]


IssueRegion = Annotated[list[float], Field(min_length=4, max_length=4)]


class ValidatorIssue(ContractModel):
    type: str
    message: str
    suggested_action: str
    region: IssueRegion | None = None


class PageValidation(ContractModel):
    page_number: int = Field(ge=1)
    status: Literal["pass", "repair_needed", "manual_review", "failed"]
    visual_score: float = Field(ge=0, le=1)
    editable_score: float = Field(ge=0, le=1)
    text_coverage_score: float = Field(ge=0, le=1)
    raster_fallback_ratio: float = Field(ge=0, le=1)
    issues: list[ValidatorIssue] = Field(default_factory=list)


class ValidatorReport(ContractModel):
    task_id: str
    attempt: int = Field(ge=1)
    pages: list[PageValidation]
