"""Audio conversion utilities for Twilio integration."""
import base64
import audioop
import numpy as np

# Twilio Media Streams use μ-law encoding at 8kHz
TWILIO_SAMPLE_RATE = 8000
TWILIO_ENCODING = "audio/x-mulaw"

# Your voice pipeline uses PCM at 24kHz
PIPELINE_SAMPLE_RATE = 24000


def mulaw_to_pcm(mulaw_data: bytes) -> np.ndarray:
    """
    Convert μ-law encoded audio (from Twilio) to PCM int16.

    Args:
        mulaw_data: Raw μ-law audio bytes at 8kHz

    Returns:
        np.ndarray: PCM audio as int16 array at 8kHz
    """
    # Decode μ-law to linear PCM (16-bit)
    pcm_data = audioop.ulaw2lin(mulaw_data, 2)  # 2 = 16-bit samples

    # Convert to numpy array
    audio_array = np.frombuffer(pcm_data, dtype=np.int16)
    return audio_array


def pcm_to_mulaw(pcm_data: np.ndarray, source_rate: int = PIPELINE_SAMPLE_RATE) -> bytes:
    """
    Convert PCM audio to μ-law encoding for Twilio.

    Args:
        pcm_data: PCM audio as int16 numpy array
        source_rate: Sample rate of the source audio (default 24kHz)

    Returns:
        bytes: μ-law encoded audio at 8kHz
    """
    # Ensure int16
    if pcm_data.dtype != np.int16:
        pcm_data = pcm_data.astype(np.int16)

    # Convert to bytes
    pcm_bytes = pcm_data.tobytes()

    # Resample from source_rate to 8kHz if needed
    if source_rate != TWILIO_SAMPLE_RATE:
        pcm_bytes, _ = audioop.ratecv(
            pcm_bytes,
            2,  # sample width (16-bit = 2 bytes)
            1,  # channels (mono)
            source_rate,
            TWILIO_SAMPLE_RATE,
            None
        )

    # Encode to μ-law
    mulaw_data = audioop.lin2ulaw(pcm_bytes, 2)
    return mulaw_data


def resample_for_pipeline(audio_8khz: np.ndarray) -> np.ndarray:
    """
    Resample 8kHz audio to 24kHz for the voice pipeline.

    Args:
        audio_8khz: Audio array at 8kHz

    Returns:
        np.ndarray: Audio array at 24kHz
    """
    # Ensure int16
    if audio_8khz.dtype != np.int16:
        audio_8khz = audio_8khz.astype(np.int16)

    pcm_bytes = audio_8khz.tobytes()

    # Resample from 8kHz to 24kHz
    resampled_bytes, _ = audioop.ratecv(
        pcm_bytes,
        2,  # sample width
        1,  # channels
        TWILIO_SAMPLE_RATE,
        PIPELINE_SAMPLE_RATE,
        None
    )

    return np.frombuffer(resampled_bytes, dtype=np.int16)


def encode_mulaw_for_twilio(mulaw_data: bytes) -> str:
    """
    Encode μ-law data as base64 for Twilio Media Streams.

    Args:
        mulaw_data: Raw μ-law bytes

    Returns:
        str: Base64 encoded string
    """
    return base64.b64encode(mulaw_data).decode('utf-8')


def decode_mulaw_from_twilio(base64_data: str) -> bytes:
    """
    Decode base64 μ-law data from Twilio Media Streams.

    Args:
        base64_data: Base64 encoded μ-law string

    Returns:
        bytes: Raw μ-law bytes
    """
    return base64.b64decode(base64_data)
