# Twilio Voice Agent Setup Guide

This guide will help you connect your AI voice agent to a Twilio phone number.

## Prerequisites

- Twilio Pro account with a phone number (you have this!)
- Your server accessible from the internet (we'll use ngrok)
- All dependencies installed

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Install and Setup ngrok

ngrok creates a secure tunnel to expose your local server to the internet.

1. **Install ngrok:**
   - Download from: https://ngrok.com/download
   - Or use homebrew: `brew install ngrok`

2. **Sign up for ngrok account** (free):
   - Visit: https://dashboard.ngrok.com/signup
   - Get your auth token from: https://dashboard.ngrok.com/get-started/your-authtoken

3. **Configure ngrok:**
   ```bash
   ngrok config add-authtoken YOUR_AUTH_TOKEN
   ```

## Step 3: Start Your Server

1. **In Terminal 1 - Start the Twilio server:**
   ```bash
   python twilio_server.py
   ```

   You should see:
   ```
   🎙️  Twilio Voice Agent Server
   Starting server on http://0.0.0.0:8000
   ```

2. **In Terminal 2 - Start ngrok:**
   ```bash
   ngrok http 8000
   ```

   You'll see output like:
   ```
   Forwarding  https://abc123.ngrok.io -> http://localhost:8000
   ```

   **Copy that https URL** (e.g., `https://abc123.ngrok.io`) - you'll need it!

## Step 4: Configure Your Twilio Phone Number

1. **Go to Twilio Console:**
   - Visit: https://console.twilio.com/
   - Navigate to: Phone Numbers > Manage > Active Numbers
   - Click on your phone number

2. **Configure Voice & Fax settings:**
   - Scroll down to "Voice & Fax" section
   - Under "A CALL COMES IN":
     - Select "Webhook"
     - Enter: `https://YOUR-NGROK-URL.ngrok.io/voice`
     - Example: `https://abc123.ngrok.io/voice`
     - HTTP Method: `POST`

3. **Save** your changes

## Step 5: Test It!

1. Call your Twilio phone number from your phone
2. You should hear: "Hello! Connecting you to our AI assistant."
3. Start talking to your AI agent!

Watch the terminal for logs:
- 📞 WebSocket connection established
- 🎤 Processing audio...
- 📝 Caller said: [your speech transcribed]
- 💬 Agent said: [agent response]

## Troubleshooting

### Issue: "Cannot connect to server"
- Make sure `twilio_server.py` is running
- Make sure ngrok is running
- Check that the Twilio webhook URL matches your ngrok URL

### Issue: "No audio being processed"
- Check that audio is being received in the server logs
- Verify your Twilio phone number is configured correctly
- Try speaking louder or waiting 2 seconds before speaking

### Issue: "Audio sounds distorted"
- This is normal for the first implementation
- The audio conversion may need tuning
- Check the server logs for errors

### Issue: "Agent not responding"
- Make sure your `.env` file has correct API keys:
  - `OPENAI_API_KEY`
  - `PINECONE_API_KEY`
  - `PINECONE_INDEX_NAME`
  - `BUSINESS_ID`

## How It Works

1. **Call arrives** → Twilio sends webhook to `/voice`
2. **TwiML response** → Tells Twilio to connect to WebSocket
3. **WebSocket opens** → Bidirectional audio stream established
4. **Audio flows**:
   - Caller speaks → Twilio sends μ-law audio → Server converts to PCM
   - Server resamples 8kHz → 24kHz for voice pipeline
   - Pipeline processes (STT → Agent → TTS)
   - Server converts response 24kHz → 8kHz → μ-law
   - Server sends back to Twilio → Caller hears response

## Audio Format Details

- **Twilio Format**: μ-law encoded, 8kHz, mono
- **Pipeline Format**: PCM int16, 24kHz, mono
- **Conversion**: Automatic via `twilio_audio_utils.py`

## Important Notes

1. **ngrok URL changes**: Free ngrok URLs change every restart. Update Twilio webhook each time!
2. **Production**: For production, deploy to a cloud server (AWS, GCP, etc.) with a stable URL
3. **Buffer size**: Currently processes 2 seconds of audio at a time. Adjust in `twilio_server.py` if needed
4. **Costs**: Twilio charges per minute for phone calls

## Next Steps

### Make it Production Ready:

1. **Deploy to cloud** (AWS, GCP, Heroku, etc.)
2. **Get a stable domain** (no more ngrok)
3. **Add error handling** and retry logic
4. **Add call logging** and analytics
5. **Implement conversation state** (remember context across utterances)
6. **Add authentication** for webhook endpoint
7. **Optimize buffer size** for lower latency

### Improve Audio Quality:

1. **Tune resampling** parameters
2. **Add noise reduction**
3. **Implement VAD** (Voice Activity Detection) for better turn-taking
4. **Reduce latency** with smaller buffers

## Useful Commands

```bash
# Start server
python twilio_server.py

# Start ngrok (in another terminal)
ngrok http 8000

# Check server health
curl http://localhost:8000/health

# View ngrok dashboard
http://localhost:4040
```

## Support

- Twilio Docs: https://www.twilio.com/docs/voice/media-streams
- ngrok Docs: https://ngrok.com/docs
- Issues: Check server logs and ngrok dashboard
