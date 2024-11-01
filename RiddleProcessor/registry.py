from typing import List
from pydantic import ValidationError
from models.history import Content
from models.registry import Riddle, RiddlesRegistry


class Registry:
    def __init__(self, json_file_path="RiddleProcessor/riddles_registry.json"):
        self.json_file_path = json_file_path
        self.data = self.load()

    def load(self) -> RiddlesRegistry:
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                json_data = f.read()
            return RiddlesRegistry.model_validate_json(json_data)
        except (FileNotFoundError, ValidationError):
            return RiddlesRegistry(root={})

    def save(self):
        with open(self.json_file_path, 'w', encoding='utf-8') as f:
            f.write(self.data.model_dump_json(indent=4))

    def add(self, lang: str, riddle: Riddle):
        if lang not in self.data.root:
            self.data.root[lang] = [riddle]
            self.save()
        elif riddle not in self.data.root[lang]:
            self.data.root[lang].append(riddle)
            self.save()

    def get(self, lang: str) -> List[Riddle]:
        return self.data.root.get(lang)

    def get_content(self, lang: str) -> List[Content]:
        riddle_registry = self.get(lang)

        if riddle_registry == None:
            return [Content(text=f"Nothing yet in the riddle registry for the lang '{lang}'")]
        else:
            out = [Content(
                text=f"Your riddle registry for language '{lang}' contains")]
            return out + [Content(text=i.text) for i in riddle_registry]
