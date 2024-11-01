from pydantic import Base64Bytes, BaseModel, HttpUrl

from models.profile import NewPlayer, OldPlayer


class ResponseContinue(BaseModel):
    player: OldPlayer
    total_riddles_correct: int
    answer_correct: bool
    transcription: str
    wav_location: HttpUrl


class ResponseRetry(BaseModel):
    player: NewPlayer


class ResponseStop(BaseModel):
    player: OldPlayer
    wav_location: HttpUrl
    transcription: str


class TTSResponse(BaseModel):
    output_file_url: HttpUrl


class PlayerVoiceChunk(BaseModel):
    player: OldPlayer
    recording: Base64Bytes
