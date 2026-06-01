from datetime import datetime

from pydantic import BaseModel, Field


class TemplatePositionOut(BaseModel):
    name: str
    description: str
    capacity: int


class TemplateOut(BaseModel):
    id: str
    name: str
    title: str
    description: str
    image_url: str | None
    positions: list[TemplatePositionOut]
    created_at: datetime
    updated_at: datetime


class TemplateFormData(BaseModel):
    title: str
    description: str
    image_url: str | None
    positions: list[TemplatePositionOut] = Field(default_factory=list)
