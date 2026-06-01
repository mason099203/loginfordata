from datetime import datetime
from typing import Literal

from pydantic import BaseModel


RegistrationAction = Literal["join", "leave"]


class RegistrationLogOut(BaseModel):
    id: str
    activity_id: str
    position_id: str
    position_name: str
    user_id: str
    user_name: str
    action: RegistrationAction
    action_label: str
    created_at: datetime
