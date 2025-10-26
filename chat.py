import asyncio
from agent import run_workflow, WorkflowInput
from agents import TResponseInputItem

async def chat_with_agent():
    """Interactive chat interface for the customer service agent."""
    print("=" * 60)
    print("Business Customer Service Agent - Chat Interface")
    print("=" * 60)
    print("Type 'quit' or 'exit' to end the conversation")
    print("=" * 60)
    print()

    # Store conversation history across messages
    conversation_history: list[TResponseInputItem] = []

    while True:
        # Get user input
        user_message = input("You: ").strip()

        if not user_message:
            continue

        if user_message.lower() in ['quit', 'exit', 'bye']:
            print("\nAgent: Thanks for chatting! Have a great day!")
            break

        # Add user message to conversation history
        conversation_history.append({
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": user_message
                }
            ]
        })

        try:
            # Run the agent with full conversation history
            from agents import Runner, RunConfig
            from agent import business_customer_service_assistant

            result = await Runner.run(
                business_customer_service_assistant,
                input=conversation_history,
                run_config=RunConfig(trace_metadata={
                    "__trace_source__": "chat-interface",
                })
            )

            # Update conversation history with the agent's response
            conversation_history.extend([item.to_input_item() for item in result.new_items])

            # Get the agent's response
            agent_response = result.final_output_as(str)

            print(f"\nAgent: {agent_response}\n")

        except Exception as e:
            print(f"\nError: {str(e)}\n")
            # Remove the failed message from history
            conversation_history.pop()

if __name__ == "__main__":
    asyncio.run(chat_with_agent())
