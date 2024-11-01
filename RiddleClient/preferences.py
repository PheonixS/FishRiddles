from uuid import UUID
from models.profile import UserPreference, UserPreferences


class Preferences:
    def __init__(self, json_path: str = 'RiddleClient/preferences.json'):
        self.json_path = json_path
        self.data = self.load()

    def get(self, id: UUID) -> UserPreference:
        for i in self.data.root:
            if i.id == id:
                return i

        raise ValueError("UUID not found")

    def save(self, profile: UserPreference):
        self.data.root.append(profile)

        with open(self.json_path, 'w') as f:
            f.write(self.data.model_dump_json(indent=4))

    def load(self) -> UserPreferences:
        try:
            with open(self.json_path, 'r') as f:
                data = f.read()
        except FileNotFoundError:
            return UserPreferences(root=[])
        
        return UserPreferences.model_validate_json(data)
