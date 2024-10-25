from faster_whisper import WhisperModel
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

class SilenceDetectedError(Exception):
    """Custom exception for handling silence-only audio files."""
    pass

class WhisperTranscriber:
    def __init__(self, model_name="medium"):
        self.model = WhisperModel(model_name, device="cuda", compute_type="float16")

    def detect_and_trim_silence(self, file_path, silence_thresh=-50, min_silence_len=500):
        """
        Trims silence from the audio file and raises an exception if only silence is detected.

        :param file_path: Path to the WAV file.
        :param silence_thresh: Silence threshold in dBFS (default: -50 dBFS).
        :param min_silence_len: Minimum silence length to be considered silence (default: 500 ms).
        :return: Trimmed audio segment if non-silence is detected, otherwise raises SilenceDetectedError.
        """
        # Load the audio file
        audio = AudioSegment.from_wav(file_path)

        # Detect non-silent chunks
        non_silent_chunks = detect_nonsilent(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh)

        if not non_silent_chunks:
            raise SilenceDetectedError("The file contains only silence or non-voice sounds.")

        # If non-silent audio is detected, combine those chunks into a new audio segment
        trimmed_audio = AudioSegment.silent(duration=0)
        for start, end in non_silent_chunks:
            trimmed_audio += audio[start:end]

        return trimmed_audio

    def transcribe(self, file_path):
        new_path = f'{file_path}.trimmed.wav'

        trimmed_audio = self.detect_and_trim_silence(file_path)
        trimmed_audio.export(new_path, format="wav")

        segments, info = self.model.transcribe(new_path, beam_size=5)
        segments = list(segments)

        if len(segments) == 0:
            raise SilenceDetectedError("No audible segment detected")

        first_segment = segments[0]
        return {
            'text': first_segment.text,
            'lang': info.language,
        }
