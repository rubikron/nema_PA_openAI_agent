"""Simple voice chat interface - Run this to talk to your agent!"""
import asyncio
from voice_agent import run_continuous_voice_chat

if __name__ == "__main__":
    print("\n🎙️  Starting Voice Chat with Customer Service Agent...")
    print("Make sure your microphone and speakers are working!\n")

    try:
        asyncio.run(run_continuous_voice_chat())
    except KeyboardInterrupt:
        print("\n\n👋 Chat ended. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\nTroubleshooting tips:")
        print("1. Make sure your microphone is connected and working")
        print("2. Check that your system audio is not muted")
        print("3. Verify you have the correct API keys in .env file")
