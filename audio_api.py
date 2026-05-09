import os
import requests
from config import GROQ_API_KEY, logger
import asyncio
import tempfile

async def transcribir_audio_groq(file_bytes: bytes) -> str:
    """
    Toma los bytes de un archivo de audio (formato OGG de Telegram) y devuelve la transcripción
    usando el modelo Whisper en Groq.
    """
    if not GROQ_API_KEY:
        logger.error("No se ha configurado GROQ_API_KEY")
        return "Error: No hay clave de API configurada para Groq."

    return await asyncio.to_thread(_sync_transcribir_audio, file_bytes)

def _sync_transcribir_audio(file_bytes: bytes) -> str:
    # Escribir temporalmente a disco porque requests necesita un archivo para upload
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}"
        }
        with open(tmp_path, "rb") as f:
            files = {
                "file": ("audio.ogg", f, "audio/ogg"),
                "model": (None, "whisper-large-v3"),
                "response_format": (None, "json"),
                "language": (None, "es") # Forzamos español para mayor precisión
            }
            r = requests.post(url, headers=headers, files=files, timeout=30)
            
        if r.status_code == 200:
            return r.json().get("text", "")
        else:
            logger.error(f"Error Groq API: {r.status_code} - {r.text}")
            return f"[Error al transcribir el audio: {r.status_code}]"
    finally:
        os.remove(tmp_path)
