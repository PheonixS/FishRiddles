from typing import List
from numpydantic import NDArray
from pydantic import Base64Bytes, Base64Str, BaseModel, Field, RootModel
from uuid import UUID


class UserProfile(BaseModel):
    id: UUID
    age: str
    confidence: float
    flag_new: bool = Field(default=False)
    encoding: NDArray

    class Config:
        arbitrary_types_allowed = True


class UserProfiles(RootModel):
    root: List[UserProfile]


class UserPreference(BaseModel):
    id: UUID
    lang: str
    voice: str


class UserPreferences(RootModel):
    root: List[UserPreference]


class BasePlayer(BaseModel):
    id: UUID
    age: str
    confidence: float

class NewPlayer(BasePlayer):
    recording: Base64Bytes

class OldPlayer(BasePlayer):
    lang: str
    voice: str
