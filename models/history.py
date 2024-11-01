from uuid import UUID
from typing import Dict, List, Literal
from pydantic import BaseModel, RootModel


class Content(BaseModel):
    type: str = "text"
    text: str


class MessageEntry(BaseModel):
    role: Literal["system", "assistant", "user"]
    content: List[Content]


class UserEntry(BaseModel):
    messages: List[MessageEntry]


class PlayerEntries(RootModel):
    root: Dict[UUID, UserEntry]
