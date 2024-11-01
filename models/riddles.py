from pydantic import BaseModel


class RiddleResponse(BaseModel):
    text: str
    riddles_correct: int
    answer_correct: bool
    player_wants_to_stop: bool
    player_wants_interesting_fact: bool
    riddle_text: str
    fact_text: str
