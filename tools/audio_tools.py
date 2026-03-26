"""
AudioTools - Transcripcion de audio (STT) y sintesis de voz (TTS).

Usa OpenAI Whisper/GPT-4o-mini-transcribe para STT y OpenAI TTS para generar audio.
Se activa automaticamente para modelos que no soportan audio nativo
(Bedrock Claude, Nova, Anthropic directo). Gemini y GPT-4o+ son multimodal nativos.
"""

import os
import tempfile
from pathlib import Path

from agno.tools import Toolkit
from agno.utils.log import logger


class AudioTools(Toolkit):
    """Herramientas de audio: transcripcion (STT) y sintesis de voz (TTS)."""

    def __init__(
        self,
        stt_model: str = "whisper-1",
        tts_model: str = "gpt-4o-mini-tts",
        tts_voice: str = "nova",
        tts_enabled: bool = False,
        auto_transcribe: bool = True,
    ):
        super().__init__(name="audio_tools")
        self.stt_model = stt_model
        self.tts_model = tts_model
        self.tts_voice = tts_voice
        self.tts_enabled = tts_enabled
        self.auto_transcribe = auto_transcribe

        self.register(self.transcribe_audio)
        if tts_enabled:
            self.register(self.text_to_speech)

    def _get_client(self):
        """Crea un cliente OpenAI bajo demanda."""
        from openai import OpenAI

        return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def transcribe_audio(self, audio_path: str) -> str:
        """Transcribe un archivo de audio a texto.

        Args:
            audio_path: Ruta al archivo de audio (mp3, wav, ogg, m4a, webm, mp4, mpeg, mpga).

        Returns:
            Texto transcrito del audio.
        """
        path = Path(audio_path)
        if not path.exists():
            return f"Error: archivo de audio no encontrado: {audio_path}"

        try:
            client = self._get_client()
            with open(path, "rb") as f:
                result = client.audio.transcriptions.create(
                    model=self.stt_model,
                    file=f,
                )
            logger.info(f"Audio transcrito ({self.stt_model}): {path.name} -> {len(result.text)} chars")
            return result.text
        except Exception as e:
            logger.error(f"Error transcribiendo audio: {e}")
            return f"Error al transcribir audio: {e}"

    def text_to_speech(self, text: str, output_path: str = "") -> str:
        """Genera un archivo de audio a partir de texto usando OpenAI TTS.

        Args:
            text: Texto a convertir en audio.
            output_path: Ruta donde guardar el audio (opcional, genera temporal si vacio).

        Returns:
            Ruta al archivo de audio generado.
        """
        if not text or not text.strip():
            return "Error: texto vacio para TTS"

        try:
            client = self._get_client()

            if not output_path:
                output_path = tempfile.mktemp(suffix=".mp3", prefix="tts_")

            response = client.audio.speech.create(
                model=self.tts_model,
                voice=self.tts_voice,
                input=text,
            )
            # Escribir bytes al archivo directamente (compatible con todas las versiones)
            with open(output_path, "wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)

            logger.info(f"TTS generado ({self.tts_model}/{self.tts_voice}): {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error generando TTS: {e}")
            return f"Error al generar audio: {e}"

    def generate_tts_bytes(self, text: str) -> tuple[bytes | None, str]:
        """Genera audio TTS y retorna (bytes, mime_type) para enviar directamente.

        Args:
            text: Texto a convertir en audio.

        Returns:
            Tupla (audio_bytes, mime_type) o (None, error_msg).
        """
        if not text or not text.strip():
            return None, "Texto vacio"

        try:
            client = self._get_client()
            response = client.audio.speech.create(
                model=self.tts_model,
                voice=self.tts_voice,
                input=text,
            )
            audio_bytes = b""
            for chunk in response.iter_bytes():
                audio_bytes += chunk

            logger.info(f"TTS bytes generados ({self.tts_model}/{self.tts_voice}): {len(audio_bytes)} bytes")
            return audio_bytes, "audio/mpeg"
        except Exception as e:
            logger.error(f"Error generando TTS bytes: {e}")
            return None, str(e)
