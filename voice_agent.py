"""Voice pipeline implementation for the customer service agent."""
import asyncio
import numpy as np
from agents.voice import VoicePipeline, SingleAgentVoiceWorkflow, AudioInput
from agents import TResponseInputItem
from agent import business_customer_service_assistant
from voice_utils import record_audio, AudioPlayer, SAMPLE_RATE


async def run_voice_interaction():
    """
    Run a single voice interaction:
    1. Record audio from microphone
    2. Process through voice pipeline (transcribe -> agent -> TTS)
    3. Play back the agent's audio response
    """
    print("\n" + "=" * 60)
    print("Voice Agent - Ready for Interaction")
    print("=" * 60)
    print("Press any key to start recording...")
    print("=" * 60)
    input()  # Wait for user to press Enter

    # Record audio
    print("\n🎤 Recording...")
    audio_data = record_audio()
    print(f"✓ Recording complete. Captured {len(audio_data)} samples")

    if len(audio_data) == 0:
        print("No audio recorded. Please try again.")
        return

    # Initialize the voice pipeline with your agent
    print("\n🔄 Processing through voice pipeline...")
    workflow = SingleAgentVoiceWorkflow(
        agent=business_customer_service_assistant
    )

    # Add callbacks to see what's happening
    async def on_transcription(event):
        print(f"\n📝 Transcribed: {event.transcript}")

    workflow.on_transcription = on_transcription

    pipeline = VoicePipeline(workflow=workflow)

    # Create AudioInput object
    audio_input = AudioInput(
        buffer=audio_data,
        frame_rate=SAMPLE_RATE,
        sample_width=2,  # int16 = 2 bytes
        channels=1  # mono
    )

    # Run the pipeline
    result = await pipeline.run(audio_input)

    # Stream the output audio and play it
    print("\n🔊 Playing agent response...")
    with AudioPlayer() as player:
        async for event in result.stream():
            if event.type == "voice_stream_event_audio":
                # Play the audio chunk
                player.add_audio(event.data)
            elif event.type == "voice_stream_event_transcript":
                # Print the agent's transcript
                print(f"\n💬 Agent said: {event.text}")
            elif event.type == "voice_stream_event_complete":
                print("\n✓ Response complete")

    print("\n" + "=" * 60)


async def run_continuous_voice_chat():
    """
    Run continuous voice chat session.
    Press Enter to record each message, type 'quit' to exit.

    Note: Each interaction is currently stateless. The agent won't remember
    previous messages in the voice session.
    """
    print("\n" + "=" * 60)
    print("Continuous Voice Chat - Customer Service Agent")
    print("=" * 60)
    print("Commands:")
    print("  - Press Enter to start recording")
    print("  - Press any key while recording to stop")
    print("  - Type 'quit' or 'exit' to end session")
    print("=" * 60)
    print("\nNote: Each voice message is processed independently")
    print("=" * 60)

    while True:
        command = input("\nPress Enter to record (or type 'quit' to exit): ").strip().lower()

        if command in ['quit', 'exit']:
            print("\n👋 Thanks for chatting! Goodbye!")
            break

        if command != '':
            continue

        # Record audio
        print("\n🎤 Recording... (press any key to stop)")
        audio_data = record_audio()

        if len(audio_data) == 0:
            print("⚠️  No audio recorded. Please try again.")
            continue

        print(f"✓ Recording complete. Processing...")

        # Initialize the voice pipeline
        workflow = SingleAgentVoiceWorkflow(
            agent=business_customer_service_assistant
        )

        # Add transcription callback
        async def on_transcription(event):
            print(f"\n📝 You said: {event.transcript}")

        workflow.on_transcription = on_transcription

        pipeline = VoicePipeline(workflow=workflow)

        try:
            # Create AudioInput object
            audio_input = AudioInput(
                buffer=audio_data,
                frame_rate=SAMPLE_RATE,
                sample_width=2,  # int16 = 2 bytes
                channels=1  # mono
            )

            # Run the pipeline
            result = await pipeline.run(audio_input)

            # Stream the output audio and play it
            print("\n🔊 Agent responding...")
            agent_response_text = ""

            with AudioPlayer() as player:
                async for event in result.stream():
                    if event.type == "voice_stream_event_audio":
                        # Play the audio chunk
                        player.add_audio(event.data)
                    elif event.type == "voice_stream_event_transcript":
                        # Collect the agent's transcript
                        agent_response_text = event.text
                    elif event.type == "voice_stream_event_complete":
                        print(f"\n💬 Agent: {agent_response_text}")
                        print("✓ Response complete")

        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            print("Please try again.")


if __name__ == "__main__":
    # Run continuous voice chat
    asyncio.run(run_continuous_voice_chat())
