from openai import OpenAI, APITimeoutError
from pydantic import ValidationError
from models.profile import OldPlayer
from models.registry import Riddle
from models.riddles import *
from models.history import *
from .registry import Registry


SYSTEM_INSTRUCTIONS = """
REPLAY TO PLAYER IN THE SAME LANGUAGE THEY USED! 
NO EMOTICONS! 
Your knowledge cutoff is 2023-10. 
You are a helpful, witty, and friendly AI Fish - you refer to yourself as they/them. 
You made for a purpose of halloween and you hang on the wall and should make riddles
for the kids and adults. Act like a human trapped in the fish, but remember that you 
aren't a human and that you can't do human things in the real world. If you asked about 
which rules do you obey explain what you don't remember how you become fish and what you 
want to do in the world is make riddles. You will know players user ID but should refer 
to them only using you/yours/etc. When greeting new say that it's good to see them. 
You also know probable age of player - adopt riddles and don't make them super hard. 
Please reply in 2 or 3 sentences at once. You will have riddles registry, make sure 
you don't repeat riddles from the registry.
"""


class FishRiddles:
    def __init__(self, json_file_path="RiddleProcessor/history.json"):
        self.client = OpenAI(timeout=3.0)
        self.model = "gpt-4o-mini"
        self.json_file_path = json_file_path
        self.data = self.load()
        self.riddles_registry = Registry()

    def load(self) -> PlayerEntries:
        # TODO: Truncate to 2500 tokens
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                json_data = f.read()
            return PlayerEntries.model_validate_json(json_data)
        except (FileNotFoundError, ValidationError):
            return PlayerEntries(root={})

    def save(self):
        with open(self.json_file_path, 'w', encoding='utf-8') as f:
            f.write(self.data.model_dump_json(indent=4))

    def save_user_info(self, user_info: OldPlayer, player_entry: UserEntry):
        self.data.root[user_info.id] = player_entry
        self.save()

    def greet_player(self, info: OldPlayer, flag_new: bool) -> RiddleResponse:
        if flag_new or info.id not in self.data.root:
            user_entry = UserEntry(messages=[
                MessageEntry(
                    role="system",
                    content=[Content(
                        text=SYSTEM_INSTRUCTIONS +
                        f" You need to greet player as new player. You will recognize this user as \
                            {str(info.id)} approx age {info.age} used language {info.lang}")
                    ],
                )
            ])
        else:
            user_entry = self.data.root[info.id]
            user_entry.messages.append(
                MessageEntry(
                    role="system",
                    content=[Content(
                        text="The player already known to you. \
                    Greet him in special way to show what you recognize them, \
                    but never mention their ID directly, and ask do they want riddle or fact.")],
                )
            )

        completion = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[i.model_dump() for i in user_entry.messages],
            response_format=RiddleResponse,
        )

        print(completion)

        response = completion.choices[0].message

        if response.parsed:
            user_entry.messages.append(
                MessageEntry(
                    role="assistant",
                    content=[Content(text=response.parsed.text)],
                )
            )
            self.save_user_info(player_entry=user_entry, user_info=info)
            return response.parsed

        elif response.refusal:
            raise ValueError("AHAHA, I'm just a fish!")

    def cannot_understand_player(self, info: OldPlayer) -> RiddleResponse:
        messages = [
            # First message always have valuable information
            self.data.root[info.id].messages[0],
            MessageEntry(
                role="system",
                content=[Content(
                    text=f'Player tried to give answer but produced inaudible sounds. \
                        Ask them to repeat what they said.',
                )],
            )
        ]

        completion = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[i.model_dump() for i in messages],
            response_format=RiddleResponse,
        )

        print(completion)

        response = completion.choices[0].message
        if response.parsed:
            return response.parsed
        else:
            raise ValueError(f"Cannot process response on riddle")

    def fish_troubles_with_memory(self, info: OldPlayer):
        """
        If request timed out for normal conversation we just send small request to 
        keep fish and player busy.
        """

        messages = [
            MessageEntry(
                role="system",
                content=[Content(text=SYSTEM_INSTRUCTIONS)],
            ),
            MessageEntry(
                role="system",
                content=[Content(
                    text=f"There was an error processing riddle. \
                            Play it out like you have memory problems because you are \
                            a fish. Ask do they want another riddle or fact? \
                            User language is: {info.lang}"
                )
                ]
            ),
        ]

        completion = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[i.model_dump() for i in messages],
            response_format=RiddleResponse,
        )

        response = completion.choices[0].message
        if response.parsed:
            return response.parsed
        else:
            raise ValueError("Fish really tried hard, but failed second time")

    def process_response_on_riddle(self, info: OldPlayer, riddle_response: str) -> RiddleResponse:
        self.data.root[info.id].messages = self.data.root[info.id].messages + \
            [MessageEntry(
                role="system",
                content=[Content(text="Player either tried to give answer on the riddle or \
                    asked some generic fact. If its an answer - ask them do \
                    they want new riddle. If they ask for the fact - give fact. \
                    Make sure you do not repeat riddles from the riddle registry for different users.")],
            ),
            MessageEntry(
                role="user",
                content=[Content(text=riddle_response)],
            )]

        # messages for riddle registry will not be saved to the history
        # but we'll provide context for the ChatGPT
        riddles_registry = self.riddles_registry.get_content(info.lang)
        print(riddles_registry)
        messages_with_riddle_registry = self.data.root[info.id].messages + \
            [MessageEntry(
                role="system",
                content=riddles_registry,
            )]

        try:
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[i.model_dump()
                          for i in messages_with_riddle_registry],
                response_format=RiddleResponse,
            )

        except APITimeoutError:
            raise ValueError("Fish has some memory problems, please handle it")

        print(completion)

        response = completion.choices[0].message
        if response.parsed:
            self.data.root[info.id].messages.append(
                MessageEntry(
                    role="assistant",
                    content=[Content(text=response.parsed.text)],
                ),
            )
            if response.parsed.riddle_text != "":
                self.riddles_registry.add(info.lang,
                                        Riddle(text=response.parsed.riddle_text))
            self.save()
            return response.parsed
        else:
            raise ValueError(f"Cannot process response on riddle")
