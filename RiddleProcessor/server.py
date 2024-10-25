import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from metadataparser import read_dict_by_key, save_or_update_dict_by_key
import time
import tempfile
import sys
from tts import AllTalkAPI
from transcribe import WhisperTranscriber, SilenceDetectedError
from fishriddles import FishRiddles
from aiohttp import web
import socketio
import logging
from dotenv import load_dotenv
import string
import random
import base64


logger = logging.getLogger(__name__)


load_dotenv()


tts = AllTalkAPI()
transcriber = WhisperTranscriber()
riddles = FishRiddles()

sio = socketio.AsyncServer(async_mode='aiohttp', transports=[
                           'websocket'], ping_timeout=60, ping_interval=10)
app = web.Application()
sio.attach(app)


def save_bytes_to_temp_file(byte_data, suffix=".wav"):
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix=suffix) as temp_file:
        temp_file.write(byte_data)
        temp_file_path = temp_file.name

    print(f"Temporary file created at: {temp_file_path}")
    return temp_file_path


def parse_language(text, possible_lang):
    if "nede" in text or "dutc" in text or "neithe" in text or "nethe" in text:
        return 'nl'

    if "eng" in text or possible_lang == 'en':
        return 'en'

    if "рус" in text or possible_lang == 'ru':
        return 'ru'

    return 'nl'


def generate_random_string(max_length=10):
    length = random.randint(1, max_length)
    random_letters = ''.join(random.choices(string.ascii_letters, k=length))

    return random_letters


def make_answer_continue(uuid: str, riddles_correct: int,
                         answer_correct: bool, wav_location: str, transcription: str) -> dict:
    return {
        "id": uuid,
        "riddles_correct": riddles_correct,
        "answer_correct": answer_correct,
        "transcription": transcription,
        "wav_location": wav_location,
    }


def make_answer_stop(uuid: str, wav_location: str, transcription: str) -> dict:
    return {
        "id": uuid,
        "wav_location": wav_location,
        "transcription": transcription,
    }


async def greet_from_chatgpt(sid, uuid, age, confidence, flag_new, lang, voice):
    resp = riddles.greet_player(
        uuid,
        age,
        confidence,
        flag_new,
        lang,
    )

    resp_tts = tts.generate_tts(
        resp.text,
        character_voice=voice,
        language=lang,
        output_file_name=generate_random_string(),
    )

    await sio.emit('say', make_answer_continue(
        uuid, resp.riddles_correct, resp.answer_correct,
        tts.get_wav_external_url(resp_tts['output_file_url']), resp.text),
        room=sid)


async def emit_error(func, sid, e):
    await sio.emit('error', {'error': f'exception in {func}: {str(e)}'}, room=sid)


async def ask_player_to_repeat(sid, uuid, lang, voice):
    riddle_response = riddles.cannot_understand_player(uuid)
    resp_tts = tts.generate_tts(
        text=riddle_response.text,
        character_voice=voice,
        language=lang,
        output_file_name=generate_random_string(),
    )

    wav_file_location = tts.get_wav_external_url(resp_tts['output_file_url'])

    await sio.emit('say',
                   make_answer_continue(uuid,
                                        riddle_response.riddles_correct,
                                        riddle_response.answer_correct,
                                        wav_file_location, riddle_response.text),
                   room=sid)


@sio.event
async def give_answer_on_riddle(sid, data_dict):
    try:
        uuid = data_dict['id']
        data = read_dict_by_key("metadata.json", uuid)
        lang = data['lang']
        voice = data['voice']

        data_wav = base64.b64decode(data_dict['wav_b64'])

        tmp_path = save_bytes_to_temp_file(data_wav)
        print(f'tmp path: {tmp_path}')

        try:
            request = transcriber.transcribe(file_path=tmp_path)
        except SilenceDetectedError:
            print("Only silence or non audible noise detected, asking to retry")
            await ask_player_to_repeat(sid, uuid, lang, voice)
            return

        request_text = request['text'].lower()
        request_lang = request['lang']

        print(f'transcribed: {request}')

        if request_lang != lang:
            print("We decoded wrong language, ask player to repeat")
            await ask_player_to_repeat(sid, uuid, lang, voice)
            return

        if request_text == "":
            print("Something wrong with transcribing, maybe just background noise?")
            await ask_player_to_repeat(sid, uuid, lang, voice)
            return

        try:
            riddle_response = riddles.process_response_on_riddle(
                uuid, request_text)
        except ValueError:
            riddle_response = riddles.fish_troubles_with_memory(
                lang=request_lang)

        resp_tts = tts.generate_tts(
            riddle_response.text,
            character_voice=voice,
            language=lang,
            output_file_name=generate_random_string(),
        )

        wav_location = tts.get_wav_external_url(resp_tts['output_file_url'])

        if riddle_response.player_wants_to_stop:
            answer = make_answer_stop(
                uuid=uuid, wav_location=wav_location, transcription=riddle_response.text)
            await sio.emit('say_no_continue', answer, room=sid)
        else:
            await sio.emit('say', make_answer_continue(
                uuid=uuid,
                riddles_correct=riddle_response.riddles_correct,
                answer_correct=riddle_response.answer_correct,
                wav_location=wav_location,
                transcription=riddle_response.text),
                room=sid)

    except Exception as e:
        await emit_error("give_answer_on_riddle", sid, e)


@sio.event
async def greet_old_player(sid, data_dict):
    try:
        id = data_dict['id']
        data = read_dict_by_key("metadata.json", id)
        lang = data['lang']
        voice = data['voice']
        age = riddles._get_age_by_id(id)
        confidence = riddles._get_confidence_by_id(id)

        await greet_from_chatgpt(sid, id, age, confidence, False, lang, voice)

    except Exception as e:
        await emit_error("greet_old_player", sid, e)


@sio.event
async def greet_new_player(sid, data_dict):
    try:
        wav_data = base64.b64decode(data_dict['wav_b64'])

        tmp_path = save_bytes_to_temp_file(wav_data)
        print(f'tmp path: {tmp_path}')

        request = transcriber.transcribe(tmp_path)
        request_text = request['text'].lower()
        request_lang = request['lang']
        print(f'transcribed: {request}')

        id = data_dict['id']
        lang = parse_language(request_text, request_lang)

        print(f'returned: {request}')

        available_voices = tts.get_available_voices()
        voice = random.choice(available_voices)

        save_or_update_dict_by_key("metadata.json", id,
                                   {
                                       "lang": lang,
                                       "voice": voice,
                                   })

        await sio.emit('save_player_language', {"id": id, "lang": lang}, room=sid)

        await greet_from_chatgpt(sid, id, data_dict['age'], data_dict['confidence'], True, lang, voice)

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
