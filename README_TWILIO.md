# Sophia AI - Twilio Voice Integration

A complete Twilio + OpenAI Realtime API integration for your AI business assistant. Call a phone number and talk to Sophia!

## Features

✅ **Real-time voice conversation** - Continuous bidirectional audio streaming
✅ **Auto-greeting** - Sophia introduces herself and the business automatically when call connects
✅ **Dynamic business detection** - Automatically detects when Pinecone data changes to a new business
✅ **Natural turn-taking** - Server-side voice activity detection (VAD)
✅ **Can be interrupted** - Stop Sophia mid-sentence if needed
✅ **Preloaded context** - All business info loaded into context for instant responses
✅ **English only** - Configured to respond only in American English

## Quick Start

### 1. Prerequisites

- Python 3.13+
- Twilio account with a phone number
- ngrok account (free tier works)
- OpenAI API key
- All environment variables set in `.env`

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the Server

**Terminal 1 - Start the voice server:**
```bash
python twilio_realtime_server.py
```

You should see:
```
📚 Loading knowledge base...
✅ Loaded XXXX characters of business information

============================================================
🎙️  Twilio + OpenAI Realtime API Server
============================================================

This uses OpenAI's Realtime API for proper streaming!
Features:
  ✓ Continuous bidirectional audio streaming
  ✓ Turn detection (knows when you stop speaking)
  ✓ Can be interrupted
  ✓ Preloaded business context for instant responses

Starting server on http://0.0.0.0:8000
============================================================
```

**Terminal 2 - Start ngrok:**
```bash
ngrok http 8000
```

Copy the `https://` URL (e.g., `https://abc123.ngrok.io`)

### 4. Configure Twilio

1. Go to: https://console.twilio.com/
2. Navigate to: **Phone Numbers** → **Manage** → **Active Numbers**
3. Click your phone number
4. Under "Voice & Fax" → "A CALL COMES IN":
   - Webhook: `https://YOUR-NGROK-URL.ngrok.io/voice`
   - HTTP Method: `POST`
5. **Save**

### 5. Test It!

Call your Twilio phone number and talk to Sophia! 📞

## How It Works

```
┌─────────────────────────────────────────┐
│  Server starts:                         │
│  - Loads business info from Pinecone    │
│  - Caches content hash for change       │
│    detection                            │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────┐
│   You call  │
│ Twilio #    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  Server checks for Pinecone updates:    │
│  - Loads fresh content                  │
│  - Compares hash to detect changes      │
│  - Uses new data if business changed    │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  WebSocket connection established       │
│  Twilio ↔ Your Server ↔ OpenAI         │
│                                          │
│  Session configured with business info  │
│  in context                             │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  Auto-greeting triggered:               │
│  - Server sends "Hi" on behalf of user  │
│  - Sophia introduces herself:           │
│    "Hi! I'm Sophia, a virtual assistant │
│     representing [Business Name]..."    │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  Audio streaming begins:                │
│                                          │
│  You speak → Twilio → Server → OpenAI  │
│  (μ-law 8kHz → PCM 24kHz conversion)    │
│                                          │
│  OpenAI processes:                       │
│  - Transcribes your speech               │
│  - Detects when you stop talking (VAD)  │
│  - Generates response INSTANTLY         │
│    (all business info already in context)│
│                                          │
│  You hear ← Twilio ← Server ← OpenAI    │
│  (PCM 24kHz → μ-law 8kHz conversion)    │
└─────────────────────────────────────────┘
```

### Why Preloaded Context?

Instead of making retrieval calls during the conversation, all business information is loaded from Pinecone and injected into the AI's context. This means:

- **Instant responses** - No pauses for "let me look that up"
- **More natural conversation** - Flows like talking to a real person
- **Lower latency** - No round-trips to the knowledge base
- **Simpler architecture** - No function calling overhead
- **Auto-updating** - Detects when Pinecone data changes between calls

## Architecture

### Files

- **`twilio_realtime_server.py`** - Main server with OpenAI Realtime API integration
- **`twilio_audio_utils.py`** - Audio format conversion utilities
- **`agent.py`** - Your existing text-based agent (used for business queries)
- **`requirements.txt`** - All dependencies

### Key Components

1. **Pinecone Knowledge Base** - All business info loaded at startup into memory
2. **Twilio Media Streams** - Sends/receives audio over WebSocket (μ-law, 8kHz)
3. **OpenAI Realtime API** - Handles STT, conversation, TTS with preloaded context (PCM16, 24kHz)
4. **Audio Conversion** - Bidirectional format conversion between Twilio and OpenAI

## Environment Variables

Make sure your `.env` file contains:

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Pinecone (for knowledge base)
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX_NAME=sophia-website-onboarding-test
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
PINECONE_HOST=https://your-index-host.pinecone.io

# Twilio (optional - only needed for outbound calls)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1234567890
```

## Customization

### Change Sophia's Personality

Edit the instructions in `twilio_realtime_server.py` (line ~77):

```python
"instructions": """You are Sophia, a friendly business PA.

CRITICAL RULES:
- Respond ONLY in American English
- Keep responses SHORT (1-2 sentences max)
...
```

### Change the Voice

Edit the voice setting in `twilio_realtime_server.py` (line ~96):

```python
"voice": "alloy",  # Options: alloy, echo, fable, onyx, nova, shimmer
```

### Change the Greeting

The greeting is now **automatically generated** by the Realtime API. Sophia reads the business name from the Pinecone knowledge base and introduces herself dynamically.

To customize the greeting format, edit the `FIRST GREETING` section in the instructions in `twilio_realtime_server.py`:

```python
FIRST GREETING (when caller says hi/hello):
Always introduce yourself properly by saying: "Hi! I'm Sophia, a virtual assistant representing [BUSINESS NAME]..."
```

The greeting delay (to prevent audio cutoff) can be adjusted:

```python
await asyncio.sleep(1.5)  # Adjust delay before greeting
```

### Adjust Turn Detection

Edit VAD settings in `twilio_realtime_server.py`:

```python
"turn_detection": {
    "type": "server_vad",
    "threshold": 0.7,           # How sensitive (0.0-1.0), higher = less sensitive
    "prefix_padding_ms": 300,   # Include before speech starts
    "silence_duration_ms": 700  # How long silence = end of turn
}
```

**Note:** The threshold is set to 0.7 (less sensitive) and silence duration to 700ms to prevent false triggers from background noise or echo after Sophia speaks.

## Troubleshooting

### No audio response

**Check logs for:**
- `🎤 User started speaking` - Audio is being received
- `📝 User said: ...` - Speech is being transcribed
- `💬 Agent: ...` - Response is being generated

**If you don't see these:**
1. Check audio is reaching OpenAI (look for errors)
2. Verify ngrok URL is correct in Twilio
3. Check OpenAI API key is valid

### Agent rambles or speaks multiple languages

This shouldn't happen with the Realtime API version, but if it does:
1. Check the instructions emphasize SHORT responses
2. Adjust turn detection sensitivity
3. Make sure you're using `twilio_realtime_server.py` not `twilio_server.py`

### Connection drops

- Free ngrok URLs change on restart - update Twilio webhook
- Check your server doesn't crash (view logs)
- Verify WebSocket stays open

### Audio quality issues

- Twilio uses 8kHz μ-law (phone quality)
- This is normal for phone calls
- Can't improve beyond phone line quality

## Monitoring

### View Active Calls

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "ok",
  "active_calls": 2
}
```

### View Logs

Watch the server terminal for real-time logs:
- 📚 Knowledge base loading (at startup and each call)
- 🔄 Knowledge base changed (when new business detected)
- 🎙️ Initial greeting triggered
- 📞 Call events
- 🎤 Speech detection
- 📝 Transcriptions
- 💬 Agent responses
- ❌ Errors

Example log for a call with updated business:
```
📞 Twilio WebSocket connection established
📚 Checking knowledge base for updates...
🔄 Knowledge base changed! Updating cached content...
✅ Updated to 3500 characters of new business information
🔌 Connecting to OpenAI Realtime API...
✅ Connected to OpenAI Realtime API
✅ OpenAI session configured
🎙️ Triggered initial greeting
💬 Agent: Hi! I'm Sophia, a virtual assistant representing...
```

### ngrok Dashboard

View HTTP traffic at: http://localhost:4040

## Production Deployment

For production use:

1. **Deploy to cloud** (AWS, GCP, Heroku, etc.)
2. **Get a stable domain** (no more ngrok)
3. **Add authentication** for webhook endpoint
4. **Set up monitoring** (error tracking, uptime)
5. **Add logging** to file/service
6. **Implement rate limiting**
7. **Add call recording** (if needed for compliance)

## Development vs Production

### Development (Current Setup)
- ✅ Uses ngrok (temporary URLs)
- ✅ Logs to console
- ✅ No authentication
- ✅ Single server instance

### Production (Recommended)
- ✅ Stable domain with SSL
- ✅ Logs to service (e.g., CloudWatch, Datadog)
- ✅ Webhook signature validation
- ✅ Load balanced, auto-scaling
- ✅ Call analytics and monitoring

## Cost Estimates

**Per minute of conversation:**
- Twilio: ~$0.013/min (inbound call)
- OpenAI Realtime API: ~$0.06/min (audio in) + ~$0.24/min (audio out)
- **Total: ~$0.31/min**

**For reference:**
- 10 min call: ~$3.10
- 100 calls/day (5 min avg): ~$155/day
- 1000 min/month: ~$310/month

## API Documentation

- **Twilio Media Streams**: https://www.twilio.com/docs/voice/media-streams
- **OpenAI Realtime API**: https://platform.openai.com/docs/guides/realtime
- **OpenAI Agents SDK**: https://github.com/openai/openai-agents

## Support

Issues? Check:
1. Server logs (`python twilio_realtime_server.py`)
2. ngrok dashboard (http://localhost:4040)
3. Twilio console error logs
4. OpenAI API status (https://status.openai.com)

## License

MIT
