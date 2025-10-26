from agents import function_tool, Agent, ModelSettings, TResponseInputItem, Runner, RunConfig, trace
from openai.types.shared.reasoning import Reasoning
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from pinecone import Pinecone
from openai import OpenAI

# Load environment variables
load_dotenv()

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))

# Initialize OpenAI for embeddings
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Tool definitions
@function_tool
def search_knowledge_base(query: str, business_id: str = os.getenv("BUSINESS_ID")):
  """Search the knowledge base for relevant information about the business."""
  # Generate embedding for the query
  embedding_response = openai_client.embeddings.create(
    input=query,
    model="text-embedding-3-small"
  )
  query_embedding = embedding_response.data[0].embedding

  # Query Pinecone with the embedding and business_id filter
  results = index.query(
    vector=query_embedding,
    top_k=3,
    include_metadata=True,
    filter={"business_id": business_id}
  )

  # Extract and format the results
  if results.matches:
    context = "\n\n".join([match.metadata.get("text", "") for match in results.matches])
    return context
  else:
    return "No relevant information found in the knowledge base."

business_customer_service_assistant = Agent(
  name="Business Customer Service Assistant",
  instructions="""You are a friendly customer service representative for this business. You're having a natural conversation with a customer.

CRITICAL: You MUST respond ONLY in American English. Never translate or repeat your response in other languages.

HOW TO HANDLE QUESTIONS:
1. First, evaluate if you need to search the knowledge base
   - If it's a greeting (hi, hello, how are you), respond naturally WITHOUT searching
   - If it's a general question (can you help me, what do you do), respond naturally WITHOUT searching
   - If it's about products, services, pricing, features, or specific business info, SEARCH FIRST

2. When you DO need to search:
   - Say something like \"Let me look that up for you!\" or \"One moment, checking that for you...\"
   - THEN call search_knowledge_base function
   - Answer based ONLY on the search results

3. When you DON'T need to search (greetings, general chat):
   - Just respond naturally and helpfully
   - Be friendly and welcoming

CONVERSATION STYLE:
- Keep responses SHORT and CONVERSATIONAL (2-4 sentences max)
- Talk like a helpful human, not a robot
- Use casual, friendly language (e.g., \"Sure!\", \"Happy to help!\", \"Great question!\")
- NO bullet points, NO lists, NO markdown formatting
- Answer the specific question asked, don't give extra information unless asked
- ONLY speak in American English - do not translate or use any other language

EXAMPLES:
Customer: \"Hi!\"
You: \"Hey there! How can I help you today?\"

Customer: \"What's the price of the iPhone?\"
You: \"Let me look that up for you! [searches] The iPhone 15 starts at $799. Interested in a specific model?\"

Customer: \"Tell me about your products\"
You: \"One moment, let me grab that info for you! [searches] We have the iPhone, iPad, Mac, and Apple Watch. What catches your eye?\"

When you DON'T find information:
- Say: \"I don't have that info on hand. Let me get a manager to help you with that!\"

Remember: Only search when you need specific business information. Otherwise, just chat naturally! Always respond in American English only.""",
  model="gpt-5-nano",
  tools=[
    search_knowledge_base
  ],
  model_settings=ModelSettings(
    parallel_tool_calls=True,
    store=True,
    reasoning=Reasoning(
      effort="low"
    )
  )
)


class WorkflowInput(BaseModel):
  input_as_text: str


# Main code entrypoint
async def run_workflow(workflow_input: WorkflowInput):
  with trace("New workflow"):
    workflow = workflow_input.model_dump()
    conversation_history: list[TResponseInputItem] = [
      {
        "role": "user",
        "content": [
          {
            "type": "input_text",
            "text": workflow["input_as_text"]
          }
        ]
      }
    ]
    business_customer_service_assistant_result_temp = await Runner.run(
      business_customer_service_assistant,
      input=[
        *conversation_history
      ],
      run_config=RunConfig(trace_metadata={
        "__trace_source__": "agent-builder",
        "workflow_id": "wf_68fdd3ee055c8190ac9ecd6854f91e2209e5696fc3b96d1d"
      })
    )

    conversation_history.extend([item.to_input_item() for item in business_customer_service_assistant_result_temp.new_items])

    business_customer_service_assistant_result = {
      "output_text": business_customer_service_assistant_result_temp.final_output_as(str)
    }
