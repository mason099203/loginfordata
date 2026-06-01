from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ActivityStatus = Literal["draft", "active", "closed"]


class PositionOut(BaseModel):
    id: str
    name: str
    description: str
    capacity: int
    participant_count: int
    is_joined: bool = False


class ActivityOut(BaseModel):
    id: str
    title: str
    description: str
    image_url: str | None
    start_time: datetime
    end_time: datetime
    status: ActivityStatus
    positions: list[PositionOut]
    created_by: str
    created_at: datetime
    updated_at: datetime
    is_live: bool = False


class PositionInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    capacity: int = Field(ge=1, le=1000)
