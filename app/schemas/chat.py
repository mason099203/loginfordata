from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RoomType = Literal["global", "activity"]


class MessageOut(BaseModel):
    id: str
    room_type: RoomType
    room_id: str | None
    sender_id: str
    sender_name: str
    content: str
    created_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
