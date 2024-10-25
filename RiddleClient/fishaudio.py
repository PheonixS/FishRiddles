import base64
from os import unlink
import tempfile
import time
import requests
import sounddevice as sd
import soundfile as sf


class FishAudio:
    def play_wav(self, file_path, blocking=True):
        data, samplerate = sf.read(file_path, dtype='float32')
        sd.play(data, samplerate)
        if blocking:
            self.wait_and_stop()

    def wait_and_stop(self):
        sd.wait()
        sd.stop()

    def count_syllables(self, word):
        vowels = "aeiouy"
        word = word.lower()
        syllable_count = 0
        if word[0] in vowels:
            syllable_count += 1
        for i in range(1, len(word)):
            if word[i] in vowels and word[i - 1] not in vowels:
                syllable_count += 1
        # Handle words with no vowels (e.g., short abbreviations)
        if syllable_count == 0:
            syllable_count = 1
        return syllable_count

    # Function to control the fish's mouth opening and closing
    def control_fish_mouth(self, callback, word_timing):
        stream = sd.get_stream()
        open_duration = 0.6   # Time to open the mouth

        for _, duration in enumerate(word_timing):
            if not stream.active:
                print("Stopping mouth control...")
                callback("mouth_close")
                sd.stop()
                break

            callback("mouth_open")

            if duration > open_duration:
                time.sleep(duration - open_duration)
            callback("mouth_close")

    # Function to distribute time based on syllable counts
    def distribute_time_by_syllables(self, wav_file_path, transcription):
        # Load the wav file to get its total duration
        audio_signal, samplerate = sf.read(wav_file_path)
        # Total duration of the wav file
        total_duration = len(audio_signal) / samplerate

        # Split transcription into words and count syllables
        words = transcription.split()
        syllable_counts = [self.count_syllables(word) for word in words]
        total_syllables = sum(syllable_counts)

        # Calculate time per syllable
        time_per_syllable = total_duration / total_syllables

        # Distribute time per word based on syllable count
        word_timing = [count * time_per_syllable for count in syllable_counts]

        return word_timing

    def say_with_callback(self, wav_path, transcription, callback):
        word_timing = self.distribute_time_by_syllables(
            wav_path, transcription)
        self.play_wav(wav_path, blocking=False)
        self.control_fish_mouth(callback=callback, word_timing=word_timing)
        sd.wait()
        sd.stop()

    def say_b64_with_callback(self, wav_b64, transcription, callback):
        audio = base64.b64decode(wav_b64)
        temp = tempfile.NamedTemporaryFile(delete=False)
        temp.write(audio)
        self.say_with_callback(temp.name, transcription, callback)
        unlink(temp.name)

    def say_from_url_with_callback(self, wav_url, transcription, callback):
        try:
            response = requests.get(wav_url)
            response.raise_for_status()
        except requests.RequestException as e:
            raise ValueError(
                f"Unable to download file from server, error was: {str(e)}")        
        
        temp = tempfile.NamedTemporaryFile(delete=False)
        temp.write(response.content)
        self.say_with_callback(temp.name, transcription, callback)
        unlink(temp.name)
