"""Twilio + OpenAI Realtime API integration for continuous voice streaming."""
import asyncio
import json
import base64
import os
import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import Response
from pinecone import Pinecone
from twilio_audio_utils import (
    decode_mulaw_from_twilio,
    mulaw_to_pcm,
    pcm_to_mulaw,
    encode_mulaw_for_twilio,
    TWILIO_SAMPLE_RATE
)

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(
    name=os.getenv("PINECONE_INDEX_NAME"),
    host=os.getenv("PINECONE_HOST")
)

def load_knowledge_base():
    """Load all content from Pinecone knowledge base."""
    # Fetch all vectors (we know there are only 4)
    # Use a zero vector to get all results
    results = index.query(
        vector=[0.0] * 1024,  # Zero vector to match all
        top_k=10,  # Get all vectors
        include_metadata=True
    )

    # Extract all text content
    content_pieces = []
    for match in results.matches:
        if match.metadata and match.metadata.get("text"):
            content_pieces.append(match.metadata["text"])

    return "\n\n---\n\n".join(content_pieces)

# Load initial knowledge base content and store hash for change detection
print("📚 Loading initial knowledge base...")
_cached_knowledge_base = load_knowledge_base()
_cached_content_hash = hash(_cached_knowledge_base)
print(f"✅ Loaded {len(_cached_knowledge_base)} characters of business information")
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"

app = FastAPI()
active_calls = {}


@app.post("/voice")
async def voice_webhook(request: Request):
    """Twilio webhook endpoint for incoming calls."""
    host = request.headers.get("host", "your-server.com")
    protocol = "wss" if "localhost" not in host else "ws"
    ws_url = f"{protocol}://{host}/media-stream"

    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}" />
    </Connect>
</Response>'''

    return Response(content=twiml, media_type="application/xml")


@app.websocket("/media-stream")
async def media_stream_handler(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams.
    Creates a bidirectional connection between Twilio and OpenAI Realtime API.
    """
    await websocket.accept()
    print("📞 Twilio WebSocket connection established")

    call_sid = None
    stream_sid = None
    openai_ws = None

    try:
        # Check for knowledge base updates
        global _cached_knowledge_base, _cached_content_hash

        print("📚 Checking knowledge base for updates...")
        fresh_content = load_knowledge_base()
        fresh_hash = hash(fresh_content)

        if fresh_hash != _cached_content_hash:
            print("🔄 Knowledge base changed! Updating cached content...")
            _cached_knowledge_base = fresh_content
            _cached_content_hash = fresh_hash
            print(f"✅ Updated to {len(fresh_content)} characters of new business information")
        else:
            print("✅ Knowledge base unchanged, using cached content")

        knowledge_base_content = _cached_knowledge_base

        # Connect to OpenAI Realtime API
        print("🔌 Connecting to OpenAI Realtime API...")
        openai_ws = await websockets.connect(
            OPENAI_REALTIME_URL,
            additional_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1"
            }
        )
        print("✅ Connected to OpenAI Realtime API")

        # Configure the session with preloaded knowledge base
        session_config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": f"""You are Sophia, a friendly virtual business assistant.

FIRST GREETING (when caller says hi/hello):
Always introduce yourself properly by saying: "Hi! I'm Sophia, a virtual assistant representing [BUSINESS NAME from the information below]. How can I help you today?"
Use the actual business name from the BUSINESS INFORMATION section.

CRITICAL RULES:
- Respond ONLY in American English
- Keep responses SHORT (1-2 sentences max)
- Never repeat yourself in other languages
- Stop talking after answering to let the customer respond
- Be conversational and helpful

You have all the business information you need below. Answer questions directly from this knowledge - no need to look anything up!

=== BUSINESS INFORMATION ===
{knowledge_base_content}
=== END BUSINESS INFORMATION ===

When answering questions:
- Use the information above to answer about products, services, pricing, contact info
- Be specific with prices and details when available
- For greetings and general chat, just respond naturally
- If something isn't in the information above, say you don't have that specific info and offer to help with something else""",
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.7,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 700
                }
            }
        }
        await openai_ws.send(json.dumps(session_config))
        print("✅ OpenAI session configured")

        # Wait for Twilio media stream to fully establish before greeting
        await asyncio.sleep(1.5)

        # Send initial greeting - simulate a user saying "hi" to trigger Sophia's introduction
        initial_message = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Hi"
                    }
                ]
            }
        }
        await openai_ws.send(json.dumps(initial_message))

        # Trigger the response so Sophia greets the caller
        await openai_ws.send(json.dumps({"type": "response.create"}))
        print("🎙️ Triggered initial greeting")

        # Create tasks for bidirectional streaming
        async def twilio_to_openai():
            """Forward audio from Twilio to OpenAI"""
            nonlocal call_sid, stream_sid

            async for message in websocket.iter_text():
                data = json.loads(message)
                event_type = data.get("event")

                if event_type == "start":
                    call_sid = data["start"]["callSid"]
                    stream_sid = data["start"]["streamSid"]
                    print(f"🎙️  Call started: {call_sid}")
                    active_calls[call_sid] = {
                        "stream_sid": stream_sid,
                        "websocket": websocket,
                        "openai_ws": openai_ws
                    }

                elif event_type == "media":
                    # Get audio from Twilio (μ-law at 8kHz)
                    payload = data["media"]["payload"]
                    mulaw_data = decode_mulaw_from_twilio(payload)
                    pcm_8khz = mulaw_to_pcm(mulaw_data)

                    # Resample from 8kHz to 24kHz for OpenAI
                    from twilio_audio_utils import resample_for_pipeline
                    pcm_24khz = resample_for_pipeline(pcm_8khz)

                    # Convert to base64 PCM16 for OpenAI
                    pcm_base64 = base64.b64encode(pcm_24khz.tobytes()).decode('utf-8')

                    # Send to OpenAI
                    audio_message = {
                        "type": "input_audio_buffer.append",
                        "audio": pcm_base64
                    }
                    await openai_ws.send(json.dumps(audio_message))

                elif event_type == "stop":
                    print(f"📞 Call ended: {call_sid}")
                    if call_sid in active_calls:
                        del active_calls[call_sid]
                    break

        async def openai_to_twilio():
            """Forward audio and events from OpenAI to Twilio"""
            async for message in openai_ws:
                event = json.loads(message)
                event_type = event.get("type")

                # Handle different event types
                if event_type == "session.created":
                    print("✅ OpenAI session created")

                elif event_type == "session.updated":
                    print("✅ OpenAI session updated")

                elif event_type == "input_audio_buffer.speech_started":
                    print("🎤 User started speaking")

                elif event_type == "input_audio_buffer.speech_stopped":
                    print("🎤 User stopped speaking")

                elif event_type == "conversation.item.input_audio_transcription.completed":
                    transcript = event.get("transcript", "")
                    print(f"📝 User said: {transcript}")

                elif event_type == "response.audio.delta":
                    # Audio chunk from OpenAI
                    audio_base64 = event.get("delta", "")
                    if audio_base64:
                        # Decode PCM16 from OpenAI
                        pcm_data = base64.b64decode(audio_base64)

                        # Convert PCM to μ-law for Twilio
                        import numpy as np
                        pcm_array = np.frombuffer(pcm_data, dtype=np.int16)

                        # Resample from 24kHz to 8kHz for Twilio
                        mulaw_data = pcm_to_mulaw(pcm_array, source_rate=24000)

                        # Send to Twilio
                        payload = encode_mulaw_for_twilio(mulaw_data)
                        media_message = {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": payload
                            }
                        }

                        if websocket.client_state.name == "CONNECTED":
                            await websocket.send_text(json.dumps(media_message))

                elif event_type == "response.audio_transcript.delta":
                    # Agent's transcript
                    delta = event.get("delta", "")
                    if delta:
                        print(f"💬 Agent: {delta}", end="", flush=True)

                elif event_type == "response.audio_transcript.done":
                    print()  # New line after transcript

                elif event_type == "error":
                    error = event.get("error", {})
                    print(f"❌ OpenAI error: {error}")

        # Run both directions concurrently
        await asyncio.gather(
            twilio_to_openai(),
            openai_to_twilio()
        )

    except Exception as e:
        print(f"❌ Error in media stream: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if openai_ws:
            await openai_ws.close()
        if call_sid and call_sid in active_calls:
            del active_calls[call_sid]
        print("📞 WebSocket closed")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "active_calls": len(active_calls)}


if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print("🎙️  Twilio + OpenAI Realtime API Server")
    print("=" * 60)
    print("\nThis uses OpenAI's Realtime API for proper streaming!")
    print("Features:")
    print("  ✓ Continuous bidirectional audio streaming")
    print("  ✓ Turn detection (knows when you stop speaking)")
    print("  ✓ Can be interrupted")
    print("  ✓ Uses your existing text agent for business queries")
    print("\nStarting server on http://0.0.0.0:8000")
    print("=" * 60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8002)
