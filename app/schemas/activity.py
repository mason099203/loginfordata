from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ActivityStatus = Literal["draft", "active", "closed"]
ActivityVisibility = Literal["public", "private"]

ACTIVATE_DURATION_OPTIONS = (1, 2, 3, 6, 12, 24)


class ParticipantOut(BaseModel):
    user_id: str
    display_name: str


class PositionOut(BaseModel):
    id: str
    name: str
    description: str
    capacity: int
    participant_count: int
    is_joined: bool = False
    participants: list[ParticipantOut] = Field(default_factory=list)


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
    total_capacity: int = 0
    total_participants: int = 0
    remaining_text: str = ""
    remaining_seconds: int = 0
    deleted_at: datetime | None = None
    visibility: ActivityVisibility = "public"
    access_code: str | None = None


class PositionInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    capacity: int = Field(ge=1, le=1000)
