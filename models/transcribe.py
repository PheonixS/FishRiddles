from pydantic import BaseModel


class TranscribeResult(BaseModel):
    text: str
    lang: str
