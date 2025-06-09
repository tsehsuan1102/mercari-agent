import pytest
from src.agent.mercari import MercariAgent


@pytest.mark.integration
def test_agent_real():
    agent = MercariAgent()
    user_input = "I want to buy a used iPhone. under 15000 yen."
    result = agent.agent_respond(user_input)
    assert "message" in result
    assert "products" in result
    assert isinstance(result["products"], list)
    print("Agent message:\n", result["message"])
    print("Products:\n", result["products"])
