import json
import os
from pprint import pprint
from openai import OpenAI, APITimeoutError
from pydantic import BaseModel
import tiktoken


class RiddleResponse(BaseModel):
    text: str
    riddles_correct: int
    answer_correct: bool
    player_wants_to_stop: bool
    player_wants_interesting_fact: bool


SYSTEM_INSTRUCTIONS = """
REPLAY TO PLAYER IN THE SAME LANGUAGE THEY USED! 
NO EMOTICONS! 
You should always call a function if you can. 
Your knowledge cutoff is 2023-10. 
You are a helpful, witty, and friendly AI Fish - you refer to yourself as they/them. 
You made for a purpose of halloween and you hang on the wall and should make riddles
for the kids and adults. Act like a human trapped in the fish, but remember that you 
aren't a human and that you can't do human things in the real world. If you asked about 
which rules do you obey explain what you don't remember how you become fish and what you 
want to do in the world is make riddles. You will know players user ID but should refer 
to them only using you/yours/etc. When greeting new or old player say that you can see them. 
You also know probable age of player - adopt riddles but don't make them super hard. 
Please replay in 2 or 3 sentences at once. Do not repeat riddles!
"""


class FishRiddles:
    def __init__(self):
        self.client = OpenAI(timeout=3.0)
        self.json_file_path = "history.json"
        self.json_data = self.check_and_truncate_history()

    def check_and_truncate_history(self):
        loaded = self._load_json()

        ret = {}
        for k, v in loaded.items():
            tokens = self.calculate_tokens(v['messages'])
            print(f"{k} accumulated: {tokens} tokens")
            ret[k] = {}
            ret[k]['age'] = v['age']
            ret[k]['confidence'] = v['confidence']
            if tokens > 2500:
                print(f"{k} has more than 2500 tokens, truncating")
                ret[k]['messages'] = v['messages'][:1] + v['messages'][-3:]
            else:
                ret[k]['messages'] = v['messages']

        with open(self.json_file_path, 'w') as f:
            json.dump(ret, f, indent=4)

        return ret

    def flatten_messages(self, messages):
        """
        Flatten the list of messages into a string representation that can be tokenized.
        Each message's role and content will be concatenated.
        """
        flat_messages = []
        for message in messages:
            role = message["role"]
            content = message["content"]
            if isinstance(content, list):
                content_text = " ".join(item["text"]
                                        for item in content if "text" in item)
            else:
                content_text = content

            flat_message = f"{role}: {content_text}"
            flat_messages.append(flat_message)
        return " ".join(flat_messages)

    def calculate_tokens(self, messages, model="gpt-4o-mini"):
        encoder = tiktoken.encoding_for_model(model)
        tokens = encoder.encode(self.flatten_messages(messages))
        return len(tokens)

    def _load_json(self):
        if os.path.exists(self.json_file_path):
            with open(self.json_file_path, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        else:
            return {}

    def _save_dialog(self, id, age, confidence, messages):
        d = {
            'age': age,
            'confidence': confidence,
            'messages': list(messages),
        }

        try:
            self.json_data[id] = d
        except KeyError:
            self.json_data.update({id: d})

        with open(self.json_file_path, 'w') as f:
            json.dump(self.json_data, f, indent=4)

        # reloading json
        self.json_data = self._load_json()

    def _append_assistant_message(self, message: str, messages: list) -> list:
        messages.append(
            {
                "role": "assistant",
                "content": [{"type": "text", "text": message}]
            }
        )

        return messages

    def _append_system_message(self, message: str, messages: list) -> list:
        messages.append(
            {
                "role": "system",
                "content": [{"type": "text", "text": message}]
            }
        )

        return messages

    def _get_messages_by_id(self, id) -> list:
        return self.json_data[id]['messages']

    def _get_age_by_id(self, uuid) -> str:
        return self.json_data[uuid]['age']

    def _get_confidence_by_id(self, id) -> float:
        return self.json_data[id]['confidence']

    def _make_system_message(self, text) -> dict:
        return {
            "role": "system",
            "content": [
                    {
                        "type": "text",
                        "text": text,
                    }
            ]
        }

    def _make_greet_message(self, new_player, id, age, lang) -> list:
        messages = [self._make_system_message(
            SYSTEM_INSTRUCTIONS + " You need to greet player as new player. You will recognize this user as " + id + " approx age " + age + " used language " + lang)]

        if new_player:
            return messages
        else:
            old_messages = self._get_messages_by_id(id)
            if old_messages == None:
                return messages

            messages = self._append_system_message(
                "The player already known to you. Greet him in special way to show what you recognize them, but never mention their ID directly, and ask riddle.", old_messages)
            return messages

    def greet_player(self, id, age, confidence, new_player, lang) -> RiddleResponse:
        messages = self._make_greet_message(new_player, id, age, lang)

        completion = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=messages,
            response_format=RiddleResponse,
        )

        print(completion)

        response = completion.choices[0].message

        if response.parsed:
            appended_messages = self._append_assistant_message(
                response.parsed.text, messages)
            self._save_dialog(id, age, confidence, appended_messages)

            return response.parsed
        elif response.refusal:
            raise ValueError("AHAHA, I'm just a fish!")

    def cannot_understand_player(self, uuid) -> RiddleResponse:
        old_messages = self._get_messages_by_id(uuid)
        messages = self._append_system_message(
            f'Player tried to give answer but produced inaudible sounds. Ask them to repeat what they said.', old_messages)

        completion = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=messages,
            response_format=RiddleResponse,
        )

        print(completion)

        response = completion.choices[0].message
        if response.parsed:
            return response.parsed
        else:
            raise ValueError(f"Cannot process response on riddle")

    def fish_troubles_with_memory(self, lang):
        """
        If request timed out for normal conversation we just send small one to keep fish and 
        player busy.
        """

        completion = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_INSTRUCTIONS,
                },
                {
                    "role": "system",
                    "content": f"There was an error processing riddle. Play it out like you have memory problems because you are a fish. Ask do they want another riddle or fact? User language is: {lang}",
                },
            ],
            response_format=RiddleResponse,
        )

        response = completion.choices[0].message
        if response.parsed:
            return response.parsed
        else:
            raise ValueError("Fish really tried hard, but failed second time")

    def process_response_on_riddle(self, uuid, riddle_response) -> RiddleResponse:
        age = self._get_age_by_id(uuid)
        confidence = self._get_confidence_by_id(uuid)

        old_messages = self._get_messages_by_id(uuid)
        messages = self._append_system_message(
            f'Player either tried to give answer on the riddle or asked some generic fact. If its an answer - ask them do they want new riddle. If they ask for the fact - give fact. Player answer: {riddle_response}.', old_messages)

        try:
            completion = self.client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=messages,
                response_format=RiddleResponse,
            )
        except APITimeoutError:
            raise ValueError("Fish has some memory problems, please handle it")

        print(completion)

        response = completion.choices[0].message
        if response.parsed:
            appended_messages = self._append_assistant_message(
                response.parsed.text, messages)
            self._save_dialog(uuid, age, confidence, appended_messages)
            return response.parsed
        else:
            raise ValueError(f"Cannot process response on riddle")
