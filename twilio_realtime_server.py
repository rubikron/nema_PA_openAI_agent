"""Twilio + OpenAI Realtime API integration for continuous voice streaming."""
import asyncio
import json
import base64
import os
import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import Response
from agents import Runner, RunConfig
from agent import business_customer_service_assistant
from twilio_audio_utils import (
    decode_mulaw_from_twilio,
    mulaw_to_pcm,
    pcm_to_mulaw,
    encode_mulaw_for_twilio,
    TWILIO_SAMPLE_RATE
)

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
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
    Creates a bidirectional connection between Twilio and OpenAI Realtime API.
    """
    await websocket.accept()
    print("📞 Twilio WebSocket connection established")

    call_sid = None
    stream_sid = None
    openai_ws = None

    try:
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

        # Configure the session
        session_config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": """You are Sophia, a friendly business PA.

CRITICAL RULES:
- Respond ONLY in American English
- Keep responses SHORT (1-2 sentences max)
- Never repeat yourself in other languages
- Stop talking after answering to let the customer respond
- Be conversational and helpful

When the user asks about business information (products, services, pricing):
- Tell them you'll look that up
- Use the get_business_info function
- Answer based on the results

For greetings and general chat:
- Just respond naturally without searching""",
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                },
                "tools": [
                    {
                        "type": "function",
                        "name": "get_business_info",
                        "description": "Search the knowledge base for business information",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "What to search for in the knowledge base"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                ],
                "tool_choice": "auto"
            }
        }
        await openai_ws.send(json.dumps(session_config))
        print("✅ OpenAI session configured")

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

                elif event_type == "response.function_call_arguments.done":
                    # Function call requested
                    call_id = event.get("call_id")
                    name = event.get("name")
                    arguments = event.get("arguments")

                    print(f"🔧 Function call: {name}({arguments})")

                    # Execute the function (call our text agent)
                    if name == "get_business_info":
                        args = json.loads(arguments)
                        query = args.get("query", "")

                        # Use our existing agent to search
                        result = await call_text_agent(query)

                        # Send result back to OpenAI
                        function_response = {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps({"result": result})
                            }
                        }
                        await openai_ws.send(json.dumps(function_response))

                        # Trigger response generation
                        await openai_ws.send(json.dumps({"type": "response.create"}))

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


async def call_text_agent(query: str) -> str:
    """
    Call the existing text-based agent to handle business queries.

    Args:
        query: The user's question

    Returns:
        The agent's response
    """
    try:
        print(f"🔍 Searching knowledge base for: {query}")

        # Run the agent
        result = await Runner.run(
            business_customer_service_assistant,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": query
                        }
                    ]
                }
            ],
            run_config=RunConfig()
        )

        # Extract the text response
        response_text = result.final_output_as(str)
        print(f"✅ Agent response: {response_text}")

        return response_text

    except Exception as e:
        print(f"❌ Error calling text agent: {str(e)}")
        return "I'm having trouble accessing that information right now. Let me get someone to help you."


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

    uvicorn.run(app, host="0.0.0.0", port=8000)
