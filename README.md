# Sophia AI Assistant - Voice-Enabled Customer Service Agent

A voice-enabled AI customer service agent that can retrieve information from your knowledge base (stored in Pinecone) and interact via text or voice.

## Features

- **Text Chat Interface**: Chat with the agent via terminal text input
- **Voice Chat Interface**: Speak to the agent and hear responses (speech-to-text and text-to-speech)
- **Knowledge Base Integration**: Retrieves relevant information from Pinecone vector database
- **Business Context Aware**: Filters results by business_id for multi-tenant support

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Or install voice features specifically:

```bash
pip install 'openai-agents[voice]' sounddevice
```

### 2. Environment Variables

Create a `.env` file with:

```
OPENAI_API_KEY=your_openai_api_key
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=us-east-1
PINECONE_INDEX_NAME=business-assistant
BUSINESS_ID=seattle-flower
```

## Usage

### Text Chat

Chat with the agent via text:

```bash
python chat.py
```

Example conversation:
```
You: Hi there!
Agent: Hey there! How can I help you today?

You: What products do you have?
Agent: Let me look that up for you! [searches knowledge base]
      We have roses, tulips, and orchids. What are you interested in?

You: quit
```

### Voice Chat

Talk to the agent using your microphone:

```bash
python voice_chat.py
```

**How it works:**
1. Press Enter to start recording
2. Speak your message
3. Press any key to stop recording
4. The agent will:
   - Transcribe your speech to text
   - Process your request (and search knowledge base if needed)
   - Convert the response to speech
   - Play the audio response
5. Repeat or type 'quit' to exit

## Architecture

### Files

- **`agent.py`**: Core agent definition with Pinecone knowledge base integration
- **`chat.py`**: Text-based chat interface
- **`voice_utils.py`**: Audio recording and playback utilities
- **`voice_agent.py`**: Voice pipeline implementation
- **`voice_chat.py`**: Main voice chat interface (run this for voice)

### How the Voice Pipeline Works

```
┌─────────────┐
│  Microphone │  You speak
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│  Speech-to-Text     │  OpenAI Transcription API
│  (Whisper)          │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Agent Processing   │  Your customer service agent
│  - Searches Pinecone│  (defined in agent.py)
│  - Generates reply  │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Text-to-Speech     │  OpenAI TTS API
│  (TTS)              │
└──────┬──────────────┘
       │
       ▼
┌─────────────┐
│  Speakers   │  You hear the response
└─────────────┘
```

### Agent Capabilities

The agent (`business_customer_service_assistant`) can:

1. **Respond naturally to greetings** without searching the knowledge base
2. **Search the knowledge base** when asked about:
   - Products and services
   - Pricing information
   - Business-specific details
3. **Maintain conversation context** across multiple turns
4. **Use conversational language** (friendly, short responses)

### Knowledge Base Search

The `search_knowledge_base` function:
- Converts your query to embeddings using `text-embedding-3-small`
- Queries Pinecone with the embedding
- Filters by `business_id` for multi-tenant support
- Returns top 3 most relevant results
- Agent uses these results to answer your question

## Preparing for Twilio Integration

This voice pipeline is designed to be integrated with Twilio for phone calls. The current implementation:

- ✅ Transcribes speech to text
- ✅ Processes requests through your agent
- ✅ Converts responses back to speech
- ✅ Maintains conversation history
- ✅ Uses industry-standard audio format (24kHz, mono, int16)

### Next Steps for Twilio

1. **WebSocket Integration**: Twilio uses WebSockets for real-time audio streaming
2. **Media Stream Handler**: Process incoming audio chunks from Twilio
3. **Bidirectional Audio**: Send TTS audio back to Twilio in real-time
4. **Call Management**: Handle call events (incoming, hangup, etc.)

The voice pipeline you have now handles the core AI logic. You'll wrap it with Twilio's WebSocket handlers to connect it to phone calls.

## Testing

### Test Text Chat
```bash
python chat.py
```

Try:
- "Hi!" (should respond naturally)
- "What do you sell?" (should search Pinecone)
- "Tell me about your prices" (should search knowledge base)

### Test Voice Chat
```bash
python voice_chat.py
```

Requirements:
- Working microphone
- Speakers or headphones
- Quiet environment for best transcription

## Troubleshooting

### Audio Issues

**No audio recording:**
- Check microphone permissions
- Verify microphone is connected
- Test with: `python -c "import sounddevice; print(sounddevice.query_devices())"`

**No audio playback:**
- Check system volume
- Verify speakers/headphones are connected
- Test output devices

### API Issues

**OpenAI errors:**
- Verify `OPENAI_API_KEY` in `.env`
- Check API quota/billing

**Pinecone errors:**
- Verify `PINECONE_API_KEY` in `.env`
- Confirm index name is correct
- Check that embeddings exist for your `BUSINESS_ID`

### Voice Pipeline Errors

**Transcription fails:**
- Audio might be too short (speak for at least 1-2 seconds)
- Check for background noise
- Verify audio format compatibility

## Development

### Adding New Tools

Edit `agent.py` to add new function tools:

```python
@function_tool
def get_hours(location: str):
    """Get business hours for a location."""
    # Your implementation
    return "We're open 9am-5pm"

# Add to agent tools list
business_customer_service_assistant = Agent(
    tools=[search_knowledge_base, get_hours]
)
```

### Customizing Voice Settings

Edit `voice_utils.py` to change audio settings:

```python
SAMPLE_RATE = 24000  # Audio sample rate
CHANNELS = 1         # Mono audio
DTYPE = np.int16     # Audio data type
```

## License

MIT
