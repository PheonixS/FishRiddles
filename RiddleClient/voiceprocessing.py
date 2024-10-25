from pyaudio import PyAudio
import speech_recognition as sr

class VoiceProcessing:
    def __init__(self, mic_index=1, sample_rate=44100, chunk_size=2048, energy_threshold=1500):
        self.p = PyAudio()
        for i in range(self.p.get_host_api_count()):
            print(self.p.get_device_info_by_index(i))

        self.r = sr.Recognizer()
        self.r.dynamic_energy_threshold = False
        self.r.energy_threshold = energy_threshold

        self.m = sr.Microphone(device_index=mic_index,
                               sample_rate=sample_rate, chunk_size=chunk_size)

    def calibrate(self, duration=1):
        with self.m as source:
            self.r.adjust_for_ambient_noise(source, duration)
            return True
        return False

    def start_background_listening(self, callback, phrase_time_limit=3):
        return self.r.listen_in_background(self.m, callback, phrase_time_limit=phrase_time_limit)

    def listen(self, phrase_time_limit=3):
        with self.m as source:
            return self.r.listen(source, phrase_time_limit=phrase_time_limit)
