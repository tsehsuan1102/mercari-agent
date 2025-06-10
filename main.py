from src.agent.mercari import MercariAgent

import os
from dotenv import load_dotenv
import asyncio

# --- load environment variables ---
load_dotenv()


async def main():
    print("Mercari Agent Test Mode: Please input your request: ")
    user_input = input("User: ")

    try:
        agent = MercariAgent(os.getenv("OPENAI_API_KEY"))
    except Exception as e:
        print(f"[Error] Failed to initialize MercariAgent: {e}")
        return
    result = await agent.agent_respond(user_input)
    print("\nAgent Output:")
    message = result["message"]
    products = result["products"]
    print("--------------------------------")
    print(message)
    print("--------------------------------")
    print(products)
    print("--------------------------------")


if __name__ == "__main__":
    asyncio.run(main())
