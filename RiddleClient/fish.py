#!/usr/bin/env python3

import asyncio
import base64
import sys
import time
import socketio

from models.profile import NewPlayer, OldPlayer, UserPreference, UserProfile
from .consts import *
from .fishcontroller import FishController, FishControllerStatuses
from .age_classifier import AgeClassifier, AgeClassifierStates
from aioprocessing import AioQueue, AioPipe, AioProcess
from .voiceprocessing import VoiceProcessing
from .fishaudio import FishAudio
from .preferences import Preferences
from models.responses import *

# Paths to the models (adjust the paths if necessary)
face_model_path = 'RiddleClient/.opencv_models/res10_300x300_ssd_iter_140000_fp16.caffemodel'
face_proto_path = 'RiddleClient/.opencv_models/deploy.prototxt'
age_model_path = 'RiddleClient/.opencv_models/age_net.caffemodel'
age_proto_path = 'RiddleClient/.opencv_models/age_deploy.prototxt'

sio = socketio.AsyncClient(logger=True)
classifyQueue = AioQueue()
puppet_parent_conn, child_conn = AioPipe()

fish_no_face = asyncio.Event()
fish_no_face.set()

voice_processing = VoiceProcessing(
    mic_index=1, sample_rate=44100, chunk_size=512, energy_threshold=18000)

fish_audio = FishAudio()
player_preferences = Preferences()


def start_classify(queue):
    classifier = AgeClassifier(
        queue=queue,
        face_model_path=face_model_path,
        face_proto_path=face_proto_path,
        age_model_path=age_model_path,
        age_proto_path=age_proto_path,
        frame_width=320,
        frame_height=240,
        process_interval=5,
        timeout_duration=5,
    )
    classifier.classify()


def posses_fish(pipe):
    fish = FishController(i2c_bus=1, pipe=pipe, device_address=0x08)
    fish.process()


def wait_for_response(pipe, expect):
    while True:
        try:
            if pipe.poll(1):
                if pipe.recv() == expect:
                    break
            else:
                print(f"still waiting for response")
                time.sleep(0.1)
        except asyncio.CancelledError:
            print("wait_for_response was cancelled.")
            break
        except EOFError:
            break
        except Exception as e:
            print(f'wait_for_response got: {str(e)}')
            break


@sio.event
async def connect():
    print('connection established')


@sio.event
async def disconnect():
    print('disconnected from server')


@sio.on('error')
async def on_error(error):
    print("Error:", error['error'])


@sio.on('say_no_continue')
async def on_say_no_continue(data):
    try:
        parsed = ResponseStop.model_validate_json(data)

        fish_audio.say_from_url_with_callback(
            parsed.wav_location, parsed.transcription, do_puppet)
        do_puppet("head_down")

    except asyncio.CancelledError:
        print("on_say_no_continue: exiting")


def do_puppet(action):
    puppet_parent_conn.send((action, ()))
    wait_for_response(puppet_parent_conn,
                      FishControllerStatuses.ACTION_COMPLETED)


def flap_fin():
    do_puppet("tail_up")
    do_puppet("tail_down")


async def capture_audio(data: ResponseContinue):
    audio_ready_event = asyncio.Event()

    def callback(_, audio):
        """Callback to handle the recognized speech."""
        global wav_data
        try:
            wav_data = audio
            print(f"Audio captured: {wav_data}")
        except Exception as e:
            print(f"Error in callback: {e}")
        finally:
            audio_ready_event.set()

    try:
        stopper = voice_processing.start_background_listening(callback)

        while not audio_ready_event.is_set():
            if fish_no_face.is_set():
                print("Face no more detected near fish - stopping voice capture")
                stopper(wait_for_stop=False)
                return

            await asyncio.sleep(0.1)

        if wav_data is not None:
            print("Sending back recognized audio...")
            voice_chunk = PlayerVoiceChunk(
                player=data.player,
                recording=base64.b64encode(wav_data.get_wav_data()),
            )
            await emit_with_retry('give_answer_on_riddle', voice_chunk.model_dump_json())

        stopper(wait_for_stop=False)
    except asyncio.CancelledError:
        print("on_say: exiting")
        stopper(wait_for_stop=False)


@sio.on('save_player_preferences')
async def on_save_player_preferences(data):
    model = UserPreference.model_validate_json(data)
    print(f"Saving user preferences for user: {model.id}")
    player_preferences.save(model)


@sio.on('say')
async def on_say(data):
    try:
        print(f'saying something')

        parsed = ResponseContinue.model_validate_json(data)

        if parsed.answer_correct:
            do_puppet("mouth_close")
            do_puppet("head_down")
            await asyncio.sleep(0.5)
            fish_audio.play_wav(
                "RiddleClient/shreksophone.wav", blocking=False)
            for _ in range(5):
                flap_fin()
                time.sleep(0.5)
            fish_audio.wait_and_stop()
            do_puppet("head_up")

        if not fish_no_face.is_set():
            fish_audio.say_from_url_with_callback(
                parsed.wav_location, parsed.transcription, do_puppet)

            await capture_audio(data=parsed)
        else:
            do_puppet("head_down")
    except Exception as e:
        print(f"on_say, exception was: {str(e)}")


@sio.on('retry_greeting')
async def on_retry_greeting(data):
    model = ResponseRetry.model_validate_json(data)
    recording_b64 = base64.b64encode(greet_new_player())
    await emit_with_retry('greet_new_player',
                          NewPlayer(
                              id=model.player.id,
                              age=model.player.age,
                              confidence=model.player.confidence,
                              recording=recording_b64,
                          ).model_dump_json())


async def retry_no_player_preferences(profile: UserProfile):
    recording_b64 = base64.b64encode(greet_new_player())
    await emit_with_retry('greet_new_player',
                          NewPlayer(
                              id=profile.id,
                              age=profile.age,
                              confidence=profile.confidence,
                              recording=recording_b64,
                          ).model_dump_json())


def greet_new_player() -> bytes:
    """
    Note: return Bytes of the player voice
    """
    fish_audio.say_with_callback(
        "RiddleClient/english.wav", "English?", do_puppet)
    time.sleep(1)
    fish_audio.say_with_callback(
        "RiddleClient/nederlands.wav", "Nederlands?", do_puppet)

    return voice_processing.listen().get_wav_data()


async def emit_with_retry(event: str, data):
    max_retries = 3
    current_retry = 0
    while current_retry < max_retries:
        try:
            await sio.emit(event, data)
            break
        except Exception as e:
            print(
                f"There was an error {str(e)} emiting '{event}', retrying, attempt {current_retry}")
            await sio.disconnect()
            await sio.connect('http://192.168.88.46:8081',  transports=['websocket'])
            current_retry += 1
            await asyncio.sleep(1.5)


async def read_from_classify_queue(classify_queue):
    player_in_front_of_camera = False

    while True:
        try:
            message = await classify_queue.coro_get()
            if 'state' in message:
                if message['state'] == AgeClassifierStates.NO_FACE_DETECTED:
                    if player_in_front_of_camera:
                        fish_no_face.set()
                        do_puppet("head_down")
                        player_in_front_of_camera = False
            elif 'id' in message:
                fish_no_face.clear()

                profile = UserProfile.model_validate(message)
                if not player_in_front_of_camera:
                    if profile.flag_new:
                        print("Greet NEW player!")
                        recording_b64 = base64.b64encode(greet_new_player())
                        player_info = NewPlayer(
                            id=profile.id,
                            age=profile.age,
                            confidence=profile.confidence,
                            recording=recording_b64,
                        )
                        await emit_with_retry('greet_new_player', player_info.model_dump_json())
                        do_puppet("head_up")
                    else:
                        print("Greet OLD player!")
                        try:
                            player_prefs = player_preferences.get(profile.id)

                            player_info = OldPlayer(
                                id=profile.id,
                                age=profile.age,
                                confidence=profile.confidence,
                                lang=player_prefs.lang,
                                voice=player_prefs.voice,
                            )
                            await emit_with_retry('greet_old_player', player_info.model_dump_json())
                        except ValueError:
                            print(
                                "We have facial pattern, but no preferences saved.")
                            print(
                                "Retrying as its new Player so sever push us user preferences back.")
                            await retry_no_player_preferences(profile)

                        await asyncio.sleep(1.5)
                        do_puppet("head_up")

                    player_in_front_of_camera = True
        except asyncio.CancelledError:
            print("read_from_classify_queue was cancelled")
            break
        except Exception as e:
            print(f"Something wrong with task: {str(e)}")


async def main():
    max_backoff = 5
    backoff = 0.1

    read_task = asyncio.create_task(read_from_classify_queue(classifyQueue))

    classify_process = AioProcess(target=start_classify, args=(classifyQueue,))
    posses_fish_process = AioProcess(target=posses_fish, args=(child_conn,))
    classify_process.start()
    posses_fish_process.start()

    while True:
        try:
            await sio.connect('http://192.168.88.46:8081',  transports=['websocket'])
            await sio.wait()
            backoff = 0.1
        except asyncio.CancelledError:
            await sio.disconnect()
            read_task.cancel()
            break
        except Exception as e:
            print(f"Exception occurred: {str(e)}")
            await sio.disconnect()
            print(f"Reconnecting in {backoff} sec...")
            await asyncio.sleep(backoff)
            if backoff == max_backoff:
                backoff = 0.1
            else:
                backoff = min(backoff * 2, max_backoff)

if __name__ == "__main__":
    if voice_processing.calibrate(duration=3):
        asyncio.run(main())
    else:
        print("Unable to calibrate microphone")
        sys.exit(1)
