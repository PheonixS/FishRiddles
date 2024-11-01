from typing import Dict, List
from pydantic import BaseModel, RootModel


class Riddle(BaseModel):
    text: str


# RiddlesRegistry lang: Riddle
class RiddlesRegistry(RootModel):
    root: Dict[str, List[Riddle]]
