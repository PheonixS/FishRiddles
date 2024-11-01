from dotenv import load_dotenv  # noqa
load_dotenv()                  # noqa

from models.responses import *
import time
import tempfile
import sys
from .tts import AllTalkAPI
from .transcribe import WhisperTranscriber, SilenceDetectedError
from models.riddles import *
from .fishriddles import FishRiddles
from aiohttp import web
import socketio
import logging
import random
import string
from models.profile import NewPlayer, OldPlayer, UserPreference


logger = logging.getLogger(__name__)


tts = AllTalkAPI()
transcriber = WhisperTranscriber()
riddles = FishRiddles()

sio = socketio.AsyncServer(async_mode='aiohttp',
                           transports=['websocket'],
                           ping_timeout=60,
                           ping_interval=10)
app = web.Application()
sio.attach(app)


def save_bytes_to_temp_file(byte_data, suffix=".wav"):
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix=suffix) as temp_file:
        temp_file.write(byte_data)
        temp_file_path = temp_file.name

    print(f"Temporary file created at: {temp_file_path}")
    return temp_file_path


def parse_language(text: str, possible_lang: str):
    if "nede" in text or "dutc" in text or "neithe" in text or "nethe" in text:
        return 'nl'

    if "eng" in text or possible_lang == 'en':
        return 'en'

    if "рус" in text or possible_lang == 'ru':
        return 'ru'

    return None


def generate_random_string(max_length=10):
    length = random.randint(1, max_length)
    random_letters = ''.join(random.choices(string.ascii_letters, k=length))

    return random_letters


async def greet_from_chatgpt(sid, info: OldPlayer, flag_new: bool):
    ai_resp = riddles.greet_player(info=info, flag_new=flag_new)

    resp_tts = tts.generate_tts_export(
        text=ai_resp.text,
        character_voice=info.voice,
        language=info.lang,
        output_file_name=generate_random_string(),
    )

    await sio.emit('say',
                   ResponseContinue(
                       player=info,
                       total_riddles_correct=ai_resp.riddles_correct,
                       answer_correct=ai_resp.answer_correct,
                       wav_location=resp_tts.output_file_url,
                       transcription=ai_resp.text).model_dump_json(),
                   room=sid)


async def emit_error(func, sid, e):
    await sio.emit('error', {'error': f'exception in {func}: {str(e)}'}, room=sid)


async def ask_player_to_repeat(sid, info: OldPlayer):
    riddle_response = riddles.cannot_understand_player(info)

    resp_tts = tts.generate_tts_export(
        text=riddle_response.text,
        character_voice=info.voice,
        language=info.lang,
        output_file_name=generate_random_string(),
    )

    await sio.emit('say',
                   ResponseContinue(
                       player=info,
                       answer_correct=riddle_response.answer_correct,
                       total_riddles_correct=riddle_response.riddles_correct,
                       transcription=riddle_response.text,
                       wav_location=resp_tts.output_file_url,
                   ).model_dump_json(),
                   room=sid)


@sio.event
async def give_answer_on_riddle(sid, data):
    try:
        model = PlayerVoiceChunk.model_validate_json(data)
        tmp_path = save_bytes_to_temp_file(model.recording)
        print(f'tmp path: {tmp_path}')

        try:
            player_response = transcriber.transcribe(file_path=tmp_path)
        except SilenceDetectedError:
            print("Only silence or non audible noise detected, asking to retry")
            await ask_player_to_repeat(sid, model.player)
            return

        print(f'transcribed: {player_response}')

        if player_response.lang != model.player.lang:
            print("We decoded wrong language, ask player to repeat")
            await ask_player_to_repeat(sid=sid, info=model.player)
            return

        if player_response.text == "":
            print("Something wrong with transcribing, maybe just background noise?")
            await ask_player_to_repeat(sid, model.player)
            return

        try:
            riddle_response = riddles.process_response_on_riddle(
                info=model.player,
                riddle_response=player_response.text,
            )
        except ValueError as e:
            print(f"riddle_response ended with error, error was: {str(e)}")
            riddle_response = riddles.fish_troubles_with_memory(
                info=model.player)

        resp_tts = tts.generate_tts_export(
            text=riddle_response.text,
            character_voice=model.player.voice,
            language=model.player.lang,
            output_file_name=generate_random_string(),
        )

        if riddle_response.player_wants_to_stop:
            resp = ResponseStop(
                player=model.player,
                wav_location=resp_tts.output_file_url,
                transcription=riddle_response.text,
            )

            await sio.emit('say_no_continue', resp.model_dump_json(), room=sid)
        else:
            resp = ResponseContinue(
                player=model.player,
                total_riddles_correct=riddle_response.riddles_correct,
                answer_correct=riddle_response.answer_correct,
                transcription=riddle_response.text,
                wav_location=resp_tts.output_file_url,
            )

            await sio.emit('say', resp.model_dump_json(), room=sid)

    except Exception as e:
        await emit_error("give_answer_on_riddle", sid, e)


@sio.event
async def greet_old_player(sid, data):
    try:
        model = OldPlayer.model_validate_json(data)
        await greet_from_chatgpt(sid=sid, info=model, flag_new=False)

    except Exception as e:
        await emit_error("greet_old_player", sid, e)


@sio.event
async def greet_new_player(sid, data):
    try:
        model = NewPlayer.model_validate_json(data)
        tmp_path = save_bytes_to_temp_file(model.recording)
        print(f'tmp path: {tmp_path}')

        try:
            transcribed = transcriber.transcribe(file_path=tmp_path)
        except SilenceDetectedError:
            print(
                "Something wrong with initial greeting, ask player again startup sequence")
            await sio.emit('retry_greeting',
                           ResponseRetry(player=model)
                           .model_dump_json(),
                           room=sid)
            return

        print(f'transcribed: {transcribed}')

        corrected_lang = parse_language(
            text=transcribed.text, possible_lang=transcribed.lang)

        if parse_language == None:
            print("we cannot recognize language, trying again")
            await sio.emit('retry_greeting',
                           ResponseRetry(player=model)
                           .model_dump_json(),
                           room=sid)
            return

        player_info = OldPlayer(
            id=model.id,
            age=model.age,
            confidence=model.confidence,
            lang=corrected_lang,
            voice=tts.get_random_voice(),
        )

        player_preferences = UserPreference(
            id=player_info.id,
            lang=corrected_lang,
            voice=player_info.voice,
        )

        await sio.emit('save_player_preferences', player_preferences.model_dump_json(), room=sid)
        await greet_from_chatgpt(sid=sid, info=player_info, flag_new=True)

    except Exception as e:
        await emit_error("greet_new_player", sid, e)


if __name__ == "__main__":
    if not tts.initialize():
        print("Failed to initialize AllTalk API.")
        sys.exit(1)

    print("AllTalk API initialized successfully.")
    print("Checking for DeepSpeed")
    if (tts.current_settings.get('deepspeed_enabled', False) == False):
        print("DeepSpeed is not enabled but required, enabling it")
        tts.set_deepspeed(True)
        print("Waiting until DeepSpeed enabled")
        time.sleep(15)
        print("Done")
    else:
        print("Enabled")

    print("Starting server")
    web.run_app(app, port=8081)
