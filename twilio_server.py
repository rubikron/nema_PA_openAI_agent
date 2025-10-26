"""Twilio Media Streams server for voice agent integration."""
import asyncio
import json
import base64
import os
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.responses import Response
import numpy as np
from agents.voice import VoicePipeline, SingleAgentVoiceWorkflow, AudioInput
from agent import business_customer_service_assistant
from twilio_audio_utils import (
    decode_mulaw_from_twilio,
    mulaw_to_pcm,
    resample_for_pipeline,
    pcm_to_mulaw,
    encode_mulaw_for_twilio,
    TWILIO_SAMPLE_RATE,
    PIPELINE_SAMPLE_RATE
)

# Load environment variables
load_dotenv()

# Optional: Load Twilio credentials for webhook validation
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

app = FastAPI()

# Track active calls
active_calls = {}


@app.post("/voice")
async def voice_webhook(request: Request):
    """
    Twilio webhook endpoint for incoming calls.
    Returns TwiML to connect the call to our WebSocket.
    """
    # Get the public URL for this server (you'll need to update this)
    # For development, you can use ngrok
    host = request.headers.get("host", "your-server.com")
    protocol = "wss" if "localhost" not in host else "ws"
    ws_url = f"{protocol}://{host}/media-stream"

    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Hi, this is Sophia, the business PA. How can I help you today?</Say>
    <Connect>
        <Stream url="{ws_url}" />
    </Connect>
</Response>'''

    return Response(content=twiml, media_type="application/xml")


@app.websocket("/media-stream")
async def media_stream_handler(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams.
    Handles bidirectional audio streaming.
    """
    await websocket.accept()
    print("📞 WebSocket connection established")

    call_sid = None
    stream_sid = None
    audio_buffer = []

    # We'll accumulate audio chunks until we have enough to process
    # Twilio sends 20ms chunks, we'll process every ~2 seconds worth
    BUFFER_SIZE = int(TWILIO_SAMPLE_RATE * 2)  # 2 seconds of audio

    try:
        async for message in websocket.iter_text():
            data = json.loads(message)
            event_type = data.get("event")

            if event_type == "start":
                # Call started
                call_sid = data["start"]["callSid"]
                stream_sid = data["start"]["streamSid"]
                print(f"🎙️  Call started: {call_sid}")
                active_calls[call_sid] = {
                    "stream_sid": stream_sid,
                    "websocket": websocket
                }

            elif event_type == "media":
                # Incoming audio from caller
                payload = data["media"]["payload"]

                # Decode μ-law audio from Twilio
                mulaw_data = decode_mulaw_from_twilio(payload)

                # Convert to PCM
                pcm_8khz = mulaw_to_pcm(mulaw_data)

                # Add to buffer
                audio_buffer.extend(pcm_8khz)

                # Process when we have enough audio
                if len(audio_buffer) >= BUFFER_SIZE:
                    print(f"🎤 Processing {len(audio_buffer)} samples...")

                    # Convert buffer to numpy array
                    audio_array = np.array(audio_buffer, dtype=np.int16)

                    # Resample to 24kHz for the pipeline
                    audio_24khz = resample_for_pipeline(audio_array)

                    # Process through voice pipeline
                    await process_audio_through_pipeline(
                        audio_24khz,
                        websocket,
                        stream_sid
                    )

                    # Clear buffer
                    audio_buffer = []

            elif event_type == "stop":
                # Call ended
                print(f"📞 Call ended: {call_sid}")
                if call_sid in active_calls:
                    del active_calls[call_sid]

    except Exception as e:
        print(f"❌ Error in media stream: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if call_sid and call_sid in active_calls:
            del active_calls[call_sid]


async def process_audio_through_pipeline(
    audio_data: np.ndarray,
    websocket: WebSocket,
    stream_sid: str
):
    """
    Process audio through the voice pipeline and stream response back to Twilio.

    Args:
        audio_data: PCM audio at 24kHz
        websocket: WebSocket connection to Twilio
        stream_sid: Twilio stream SID
    """
    try:
        # Initialize the voice pipeline
        workflow = SingleAgentVoiceWorkflow(
            agent=business_customer_service_assistant
        )

        # Add transcription callback
        async def on_transcription(event):
            print(f"📝 Caller said: {event.transcript}")

        workflow.on_transcription = on_transcription

        pipeline = VoicePipeline(workflow=workflow)

        # Create AudioInput
        audio_input = AudioInput(
            buffer=audio_data,
            frame_rate=PIPELINE_SAMPLE_RATE,
            sample_width=2,  # int16 = 2 bytes
            channels=1  # mono
        )

        # Run the pipeline
        result = await pipeline.run(audio_input)

        # Stream the response back to Twilio
        print("🔊 Streaming response to caller...")
        async for event in result.stream():
            try:
                if event.type == "voice_stream_event_audio":
                    # Convert PCM audio (24kHz) to μ-law (8kHz) for Twilio
                    pcm_array = np.frombuffer(event.data, dtype=np.int16)
                    mulaw_data = pcm_to_mulaw(pcm_array, source_rate=PIPELINE_SAMPLE_RATE)

                    # Encode as base64
                    payload = encode_mulaw_for_twilio(mulaw_data)

                    # Send to Twilio
                    media_message = {
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {
                            "payload": payload
                        }
                    }

                    # Check if websocket is still connected before sending
                    if websocket.client_state.name == "CONNECTED":
                        await websocket.send_text(json.dumps(media_message))
                    else:
                        print("⚠️  WebSocket disconnected, stopping stream")
                        break

                elif event.type == "voice_stream_event_transcript":
                    print(f"💬 Agent said: {event.text}")

                elif event.type == "voice_stream_event_complete":
                    print("✓ Response complete")

            except Exception as send_error:
                print(f"⚠️  Error sending audio chunk: {send_error}")
                break

    except Exception as e:
        print(f"❌ Error processing audio: {str(e)}")
        import traceback
        traceback.print_exc()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "active_calls": len(active_calls)}


if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print("🎙️  Twilio Voice Agent Server")
    print("=" * 60)

    # Check for Twilio credentials
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        print(f"✓ Twilio Account SID: {TWILIO_ACCOUNT_SID[:10]}...")
        if TWILIO_PHONE_NUMBER:
            print(f"✓ Twilio Phone Number: {TWILIO_PHONE_NUMBER}")
    else:
        print("⚠️  No Twilio credentials found in .env")
        print("   (Optional - only needed for outbound calls and webhook validation)")

    print("\nStarting server on http://0.0.0.0:8000")
    print("\n⚠️  IMPORTANT: For Twilio to reach your server, you need to:")
    print("1. Use ngrok or similar to expose this to the internet")
    print("2. Update your Twilio phone number's webhook URL")
    print("\nExample ngrok command:")
    print("  ngrok http 8000")
    print("=" * 60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
