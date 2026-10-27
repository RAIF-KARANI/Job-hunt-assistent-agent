"""
Phase 0 check: can we talk to the LLM?

Run:  python hello_llm.py

What happens:
  1. get_llm() builds a chat model from your .env settings.
  2. We send it a list of messages:
       - SystemMessage = instructions/persona for the model
       - HumanMessage  = what the user says
  3. .invoke() sends them and waits for the reply (an AIMessage).
"""

from langchain_core.messages import HumanMessage, SystemMessage

from job_agent.llm import get_llm

llm = get_llm()
print(f"Using model: {llm.model if hasattr(llm, 'model') else llm}\n")

messages = [
    SystemMessage(content="You are a helpful career coach. Answer in 2 sentences."),
    HumanMessage(content="What makes a cover note stand out?"),
]

reply = llm.invoke(messages)

print("Reply:")
print(reply.content)
