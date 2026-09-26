"""
Quick text-only test for the LangChain RAG agent, before adding voice.
"""
from dotenv import load_dotenv
load_dotenv()

from langchain_agent import lauki_agent

def main():
    print("=== Lauki Phones Agent (text test) ===")
    print("Type your question. Type 'quit' to exit.\n")

    while True:
        question = input("You: ").strip()
        if not question:
            continue
        if question.lower() in {"quit", "exit", "q"}:
            break

        result = lauki_agent.invoke({"messages": [("user", question)]})

        # Print the last message's content (the agent's final answer)
        last_message = result["messages"][-1]
        print(f"\nAgent: {last_message.content}\n")

if __name__ == "__main__":
    main()
