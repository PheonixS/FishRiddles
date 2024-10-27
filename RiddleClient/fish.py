#!/usr/bin/env python3

import asyncio
import base64
import json
import random
import sys
import time
import socketio
from consts import *
from fishcontroller import FishController, FishControllerStatuses
from age_classifier import AgeClassifier, AgeClassifierStates
from aioprocessing import AioQueue, AioPipe, AioProcess
from voiceprocessing import VoiceProcessing
from metadataparser import read_dict_by_key, save_or_update_dict_by_key
from fishaudio import FishAudio

# Paths to the models (adjust the paths if necessary)
face_model_path = '.opencv_models/res10_300x300_ssd_iter_140000_fp16.caffemodel'
face_proto_path = '.opencv_models/deploy.prototxt'
age_model_path = '.opencv_models/age_net.caffemodel'
age_proto_path = '.opencv_models/age_deploy.prototxt'

sio = socketio.AsyncClient(logger=True, engineio_logger=True)
classifyQueue = AioQueue()
puppet_parent_conn, child_conn = AioPipe()

fish_no_face = asyncio.Event()
fish_no_face.set()

voice_processing = VoiceProcessing(
    mic_index=1, sample_rate=44100, chunk_size=512, energy_threshold=18000)

fish_audio = FishAudio()


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
        timeout_duration=3,
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


@sio.on('processed')
async def on_processed(data):
    print("Server response:", data['message'])


@sio.on('error')
async def on_error(error):
    print("Error:", error['error'])


@sio.on('save_player_language')
async def on_save_player_language(data):
    print(f'saving player language: {json.dumps(data)}')
    save_or_update_dict_by_key("metadata.json", data['id'], {
                               "lang": data['lang']})


@sio.on('save_player_progress')
async def on_save_player_progress(data):
    print(f'saving player progress: {json.dumps(data)}')

    save_or_update_dict_by_key("metadata.json", data['id'], {
                               "lang": data['lang']})


def make_payload(uuid, wav_data):
    return {
        "id": str(uuid),
        "wav_b64": base64.b64encode(wav_data)
    }


@sio.on('say_no_continue')
async def on_say_no_continue(data):
    try:
        fish_audio.say_from_url_with_callback(
            data['wav_location'], data['transcription'], do_puppet)
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


async def capture_audio(data):
    uuid = data['id']

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
            await asyncio.sleep(0.1)

        if wav_data is not None:
            print("Sending back recognized audio...")
            await sio.emit('give_answer_on_riddle', make_payload(uuid, wav_data.get_wav_data()))

        stopper(wait_for_stop=False)
    except asyncio.CancelledError:
        print("on_say: exiting")
        stopper(wait_for_stop=False)


@sio.on('say')
async def on_say(data):
    print(f'saying something')

    if data['answer_correct']:
        do_puppet("mouth_close")
        do_puppet("head_down")
        await asyncio.sleep(0.5)
        fish_audio.play_wav("shreksophone.wav", blocking=False)
        for _ in range(5):
            flap_fin()
            time.sleep(0.5)
        fish_audio.wait_and_stop()
        do_puppet("head_up")

    if not fish_no_face.is_set():
        fish_audio.say_from_url_with_callback(
            data['wav_location'], data['transcription'], do_puppet)

        await capture_audio(data)
    else:
        do_puppet("head_down")


def greet_new_player(message):
    fish_audio.say_with_callback("english.wav", "English?", do_puppet)
    time.sleep(1)
    fish_audio.say_with_callback("nederlands.wav", "Nederlands?", do_puppet)

    data_wav = voice_processing.listen().get_wav_data()
    message['wav_b64'] = base64.b64encode(data_wav)
    return message


async def read_from_classify_queue(classify_queue):
    player_was_before = False

    while True:
        try:
            message = await classify_queue.coro_get()
            if 'state' in message:
                if message['state'] == AgeClassifierStates.NO_FACE_DETECTED:
                    if player_was_before:
                        do_puppet("head_down")
                        player_was_before = False
                        fish_no_face.set()
            elif 'id' in message:
                fish_no_face.clear()
                if not player_was_before:
                    try:
                        data = read_dict_by_key("metadata.json", message['id'])
                        if data:
                            print("Greet old player!")

                            message['lang'] = data['lang']
                            await sio.emit('greet_old_player', message)
                            await asyncio.sleep(1.5)
                            do_puppet("head_up")
                        else:
                            await sio.emit('greet_new_player', greet_new_player(message))
                    except (FileNotFoundError, ValueError, IOError):
                        print("Greet new player (or data currupted :| )!")

                        await sio.emit('greet_new_player', greet_new_player(message))
                        do_puppet("head_up")

                    player_was_before = True
        except asyncio.CancelledError:
            print("read_from_classify_queue was cancelled")
            break
        except Exception as e:
            print(f"Something wrong with task: {str(e)}")


async def main():
    read_task = asyncio.create_task(read_from_classify_queue(classifyQueue))

    classify_process = AioProcess(target=start_classify, args=(classifyQueue,))
    posses_fish_process = AioProcess(target=posses_fish, args=(child_conn,))
    classify_process.start()
    posses_fish_process.start()

    try:
        await sio.connect('http://192.168.88.46:8081',  transports=['websocket'])
        await sio.wait()
    except asyncio.CancelledError:
        await sio.disconnect()
        read_task.cancel()
        import threading
        print(threading.enumerate())

if __name__ == "__main__":
    if voice_processing.calibrate(duration=3):
        asyncio.run(main())
    else:
        print("Unable to calibrate microphone")
        sys.exit(1)
