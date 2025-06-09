from src.agent.mercari import MercariAgent

import os
from dotenv import load_dotenv

# --- load environment variables ---
load_dotenv()

if __name__ == "__main__":
    print("Mercari Agent Test Mode: Please input your request: ")
    user_input = input("User: ")

    agent = MercariAgent(os.getenv("OPENAI_API_KEY"))
    result = agent.agent_respond(user_input)
    print("\nAgent Output:")
    message = result["message"]
    products = result["products"]
    print(message)
    # print(products)
