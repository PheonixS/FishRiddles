import pyaudio
import io
import requests
import time
import json
from pprint import pprint
import urllib


class AllTalkAPI:
    """
    A class to interact with the AllTalk API.
    This class provides methods to initialize the connection, fetch server information,
    and perform various operations like generating TTS, switching models, etc.
    """

    def __init__(self, config_file='config.json'):
        """
        Initialize the AllTalkAPI class.
        Loads configuration from a file or uses default values.
        Sets up the base URL for API requests and initializes variables for storing server data.
        """
        # Default configuration
        default_config = {
            "api_alltalk_protocol": "http://",
            "api_alltalk_ip_port": "127.0.0.1:7851",
            "api_alltalk_external_protocol": "http://",
            "api_alltalk_external_ip_port": "127.0.0.1:7851",
            "api_connection_timeout": 15,
        }

        # Try to load configuration from JSON file, use defaults if file not found
        try:
            with open(config_file, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            print(
                f"Config file '{config_file}' not found. Using default configuration.")
            self.config = default_config

        # Construct the base URL for API requests
        self.base_url = f"{self.config['api_alltalk_protocol']}{self.config['api_alltalk_ip_port']}"
        self.external_base_url = f"{self.config['api_alltalk_external_protocol']}{self.config['api_alltalk_external_ip_port']}"

        # Initialize variables to store API data
        self.current_settings = None
        self.available_voices = None
        self.available_rvc_voices = None

        self.pyaudio_format = pyaudio.paInt16
        self.pyaudio_channels = 1
        self.pyaudio_rate = 24000
        self.pyaudio_chunk = 1024

        self.p = pyaudio.PyAudio()

    def _open_stream(self):
        return self.p.open(format=self.pyaudio_format,
                           channels=self.pyaudio_channels,
                           rate=self.pyaudio_rate,
                           output=True)

    def check_server_ready(self):
        """
        Check if the AllTalk server is ready to accept requests.
        Attempts to connect to the server within the specified timeout period.
        Returns True if the server is ready, False otherwise.
        """
        timeout = time.time() + self.config['api_connection_timeout']
        while time.time() < timeout:
            try:
                response = requests.get(
                    f"{self.base_url}/api/ready", timeout=1)
                if response.text == "Ready":
                    return True
            except requests.RequestException:
                pass
            time.sleep(0.5)
        return False

    def initialize(self):
        """
        Perform initial setup by fetching current settings and available voices.
        This method should be called after creating an instance of AllTalkAPI.
        Returns True if initialization is successful, False otherwise.
        """
        if not self.check_server_ready():
            print("Server is offline or not responding.")
            return False

        self.current_settings = self.get_current_settings()
        self.available_voices = self.get_available_voices()
        self.available_rvc_voices = self.get_available_rvc_voices()
        return True

    def get_current_settings(self):
        """
        Fetch current settings from the AllTalk server.
        Returns a dictionary of server settings or None if the request fails.
        """
        try:
            response = requests.get(f"{self.base_url}/api/currentsettings")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching current settings: {e}")
            return None

    def get_wav(self, output_file_url):
        try:
            response = requests.get(f"{self.base_url}{output_file_url}")
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            raise ValueError(
                f"Unable to download file from server, error was: {str(e)}")

    def get_wav_external_url(self, output_file_url):
        return f"{self.external_base_url}{output_file_url}"

    def get_available_voices(self):
        """
        Fetch available voices from the AllTalk server.
        Returns a list of available voices or None if the request fails.
        """
        try:
            response = requests.get(f"{self.base_url}/api/voices")
            response.raise_for_status()
            data = response.json()
            return sorted(data.get('voices', []))
        except requests.RequestException as e:
            print(f"Error fetching available voices: {e}")
            return None

    def get_available_rvc_voices(self):
        """
        Fetch available RVC voices from the AllTalk server.
        RVC (Retrieval-based Voice Conversion) voices are used for voice cloning.
        Returns a list of available RVC voices or None if the request fails.
        """
        try:
            response = requests.get(f"{self.base_url}/api/rvcvoices")
            response.raise_for_status()
            data = response.json()
            return data.get('rvcvoices', [])
        except requests.RequestException as e:
            print(f"Error fetching available RVC voices: {e}")
            return None

    def reload_config(self):
        """
        Reload the AllTalk server configuration.
        This method triggers a config reload on the server and then re-initializes the local data.
        Returns True if the reload is successful, False otherwise.
        """
        response = requests.get(f"{self.base_url}/api/reload_config")
        if response.status_code == 200:
            # Re-fetch settings and voices after reloading config
            self.initialize()
            return True
        return False

    def generate_tts(self, text, character_voice, narrator_voice=None, **kwargs):
        """
        Generate text-to-speech audio using the AllTalk server.

        Args:
            text (str): The text to convert to speech.
            character_voice (str): The voice to use for the character.
            narrator_voice (str, optional): The voice to use for the narrator, if applicable.
            **kwargs: Additional parameters for TTS generation (e.g., language, output_file_name).

        Returns:
            dict: A dictionary containing information about the generated audio.
        Throws:
            ValueError: if processing fails
        """
        data = {
            "text_input": text,
            "character_voice_gen": character_voice,
            "narrator_enabled": "true" if narrator_voice else "false",
            "narrator_voice_gen": narrator_voice,
            **kwargs
        }
        response = requests.post(
            f"{self.base_url}/api/tts-generate", data=data)
        if response.status_code == 200:
            return response.json()
        else:
            raise ValueError(f"Unable to generate TTS")

    def generate_tts_realtime(self, text, voice, **kwargs):
        data = {
            "text": text,
            "voice": voice,
            **kwargs
        }
        response = requests.get(
            f"{self.base_url}/api/tts-generate-streaming?{urllib.parse.urlencode(data)}", stream=True)
        if response.status_code != 200:
            pprint(response.request.headers)
            print(f"error: {response.headers} {response}")
            return

        audio_stream = self._open_stream()
        response_audio_stream = io.BytesIO()

        buffer_size = 1024 * 32
        for chunk in response.iter_content(chunk_size=buffer_size):
            if chunk:
                response_audio_stream.write(chunk)

                if response_audio_stream.tell() > buffer_size:
                    response_audio_stream.seek(0)

                    audio_stream.write(response_audio_stream.read())

                    response_audio_stream.seek(0)
                    response_audio_stream.truncate(0)

        if response_audio_stream.tell() > 0:
            response_audio_stream.seek(0)
            audio_stream.write(response_audio_stream.read())

        time.sleep(0.5)

        audio_stream.stop_stream()
        audio_stream.close()

    def stop_generation(self):
        """
        Stop the current TTS generation process.
        Returns the server's response as a dictionary, or None if the request fails.
        """
        response = requests.put(f"{self.base_url}/api/stop-generation")
        return response.json() if response.status_code == 200 else None

    def switch_model(self, model_name):
        """
        Switch to a different TTS model.

        Args:
            model_name (str): The name of the model to switch to.

        Returns:
            dict: The server's response as a dictionary if successful, None if the request fails.
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/reload", params={"tts_method": model_name})
            response.raise_for_status()  # This will raise an exception for HTTP errors
            return response.json()
        except requests.RequestException as e:
            print(f"Error switching model: {e}")
            if response.status_code == 404:
                print(f"Model '{model_name}' not found on the server.")
            elif response.status_code == 500:
                print("Server encountered an error while switching models.")
            else:
                print(
                    f"Unexpected error occurred. Status code: {response.status_code}")
            return None

    def set_deepspeed(self, enabled):
        """
        Enable or disable DeepSpeed mode.
        DeepSpeed is an optimization library for large-scale models.

        Args:
            enabled (bool): True to enable DeepSpeed, False to disable.

        Returns:
            dict: The server's response as a dictionary, or None if the request fails.
        """
        response = requests.post(
            f"{self.base_url}/api/deepspeed", params={"new_deepspeed_value": str(enabled).lower()})
        return response.json() if response.status_code == 200 else None

    def set_low_vram(self, enabled):
        """
        Enable or disable Low VRAM mode.
        Low VRAM mode optimizes memory usage for systems with limited GPU memory.

        Args:
            enabled (bool): True to enable Low VRAM mode, False to disable.

        Returns:
            dict: The server's response as a dictionary, or None if the request fails.
        """
        response = requests.post(f"{self.base_url}/api/lowvramsetting",
                                 params={"new_low_vram_value": str(enabled).lower()})
        return response.json() if response.status_code == 200 else None

    def display_server_info(self):
        """
        Display all information pulled from the AllTalk server.
        This includes current settings, available voices, RVC voices, and server capabilities.
        """
        print("=== AllTalk Server Information ===")

        print(f"\nServer URL: {self.base_url}")

        print("\n--- Current Settings ---")
        pprint(self.current_settings)

        print("\n--- Available Voices ---")
        pprint(self.available_voices)

        print("\n--- Available RVC Voices ---")
        pprint(self.available_rvc_voices)

        print("\n--- Server Capabilities ---")
        if self.current_settings:
            capabilities = {
                "DeepSpeed Capable": self.current_settings.get('deepspeed_capable', False),
                "DeepSpeed Enabled": self.current_settings.get('deepspeed_enabled', False),
                "Low VRAM Capable": self.current_settings.get('lowvram_capable', False),
                "Low VRAM Enabled": self.current_settings.get('lowvram_enabled', False),
                "Generation Speed Capable": self.current_settings.get('generationspeed_capable', False),
                "Current Generation Speed": self.current_settings.get('generationspeed_set', 'N/A'),
                "Pitch Capable": self.current_settings.get('pitch_capable', False),
                "Current Pitch": self.current_settings.get('pitch_set', 'N/A'),
                "Temperature Capable": self.current_settings.get('temperature_capable', False),
                "Current Temperature": self.current_settings.get('temperature_set', 'N/A'),
                "Streaming Capable": self.current_settings.get('streaming_capable', False),
                "Multi-voice Capable": self.current_settings.get('multivoice_capable', False),
                "Multi-model Capable": self.current_settings.get('multimodel_capable', False),
                "Languages Capable": self.current_settings.get('languages_capable', False)
            }
            pprint(capabilities)
        else:
            print(
                "Server settings not available. Make sure the server is running and accessible.")
