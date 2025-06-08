from src.agent.parse_request import agent_respond

if __name__ == "__main__":
    print("Mercari Agent Test Mode: Please input your request: ")
    user_input = input("User: ")
    result = agent_respond(user_input)
    print("\nAgent Output:")
    print(result)
