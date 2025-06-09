import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from src.scraper.mercari_scraper import search_mercari
from enum import Enum


class GPTModel(str, Enum):
    GPT_4_1_MINI = "gpt-4.1-mini"
    GPT_4_1_NANO = "gpt-4.1-nano"


# --- load environment variables ---
load_dotenv()

# --- Mercari search tool schema for OpenAI function calling ---
mercari_search_tool = {
    "type": "function",
    "name": "mercari_search",
    "description": (
        "Search Mercari for products based on user criteria. "
        "Returns a list of product dicts. "
        "Only include parameters that are explicitly mentioned or implied in the user's request. "
        "Do not generate or fill in any parameters that the user did not mention. "
        "Leave all other parameters unset. "
        "Infer filters strictly from the user's input."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "Search keyword(s)"},
            "excludeKeyword": {"type": "string", "description": "Exclude keyword(s)"},
            "sort": {
                "type": "string",
                "description": "Sort type. One of: SORT_CREATED_TIME, SORT_SCORE, SORT_PRICE, SORT_NUM_LIKES",
                "enum": [
                    "SORT_CREATED_TIME",
                    "SORT_SCORE",
                    "SORT_PRICE",
                    "SORT_NUM_LIKES",
                ],
            },
            "order": {
                "type": "string",
                "description": "Order type, e.g. ORDER_DESC, ORDER_ASC",
                "enum": [
                    "ORDER_DESC",
                    "ORDER_ASC",
                ],
            },
            # "status": {
            #     "type": "array",
            #     "items": {"type": "string", "enum": ["OPENED", "SOLD_OUT"]},
            #     "description": "Product status (OPENED,)",
            # },
            "categoryId": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Category ID(s)",
            },
            "priceMin": {"type": "integer", "description": "Minimum price"},
            "priceMax": {"type": "integer", "description": "Maximum price"},
            "itemConditionId": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "1",  # 新品、未使用
                        "2",  # 未使用に近い
                        "3",  # 目立った傷や汚れなし
                        "4",  # やや傷や汚れあり
                        "5",  # 傷や汚れあり
                        "6",  # 全体的に状態が悪い
                    ],
                },
                "description": "Item condition: 1=新品・未使用, 2=未使用に近い, 3=目立った傷や汚れなし, 4=やや傷や汚れあり, 5=傷や汚れあり, 6=全体的に状態が悪い",
            },
            "itemTypes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Item types",
            },
        },
        "required": ["keyword"],
        "additionalProperties": False,
    },
}

get_recommend_product_tool = {
    "type": "function",
    "name": "get_recommend_product",
    "description": "Given a list of products and user needs, select the top 3 recommended products and provide reasons. Return a list of product dicts.",
    "parameters": {
        "type": "object",
        "properties": {
            "products": {
                "type": "array",
                "items": {"type": "object"},
                "description": "List of product dicts to choose from",
            },
            "user_request": {
                "type": "string",
                "description": "User's shopping request",
            },
        },
        "required": ["products", "user_request"],
        "additionalProperties": False,
    },
}


class MercariAgent:
    def __init__(self, openai_api_key: str = None):
        if openai_api_key is None:
            openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not set in environment.")
        self.client = OpenAI(api_key=openai_api_key)
        self.all_results = {}

    def agent_respond(self, user_input: str) -> dict:
        system_prompt = str(
            "\n".join(
                [
                    "You are a helpful shopping assistant for Mercari Japan. ",
                    "You can use the 'mercari_search' tool to search for products based on user needs. ",
                    "You can also use the 'get_recommend_product' tool to select the top 3 recommended products from a list. ",
                    "After using the tools, summarize the recommendations in a concise way. ",
                    # Markdown table with columns: Name, Price, Reason, Link, Image. "
                    # "Be persuasive and user-friendly in your explanations.",
                ]
            )
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
        tools = [mercari_search_tool]
        self.all_results = {}

        while True:
            response = self.client.responses.create(
                model=GPTModel.GPT_4_1_MINI, input=messages, tools=tools
            )
            output = response.output[0]
            print(output)
            if getattr(output, "type", None) == "function_call":
                function_name = getattr(output, "name", None)
                call_id = getattr(output, "call_id", None)
                args = json.loads(getattr(output, "arguments", "{}"))
                print("### [Tool name]: ", function_name)
                print("### [Args]: ", args)
                if function_name == "mercari_search":
                    mercari_items = search_mercari(args)
                    search_results = [
                        {
                            "name": item.name,
                            "price": item.price,
                            "image": item.image,
                            "url": item.url,
                            "item_id": item.item_id,
                            "itemtype": item.itemtype,
                        }
                        for item in mercari_items
                    ]
                    self.all_results["search_results"] = search_results
                    messages.append(output)
                    messages.append(
                        {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps(search_results),
                        }
                    )
                    top_products = self.recommend_products(
                        user_input, search_results, GPTModel.GPT_4_1_MINI, 3
                    )
                    self.all_results["top3"] = top_products.get("products", [])
                    messages.append(
                        {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps(top_products),
                        }
                    )
                else:
                    # unknown tool, break
                    break
            else:
                # LLM output final message
                message = getattr(output, "content", "")
                # return top3 products (if any) and all products
                return {
                    "message": message,
                    "products": self.all_results.get("top3", []),
                    # "raw_results": self.all_results.get("search_results", []),
                }

    def recommend_products(
        self, user_input: str, search_results: list, model: str, k: int = 3
    ) -> dict:
        """
        Use LLM to pick and recommend the top 3 products from all search results, and return as a JSON list of item_id.
        """
        system_prompt = (
            "You are a helpful shopping assistant for Mercari Japan. "
            "You will receive a list of products from Mercari and a user's shopping request. "
            f"Please pick the top {k} products that best match the user's needs, and directly return a JSON list of their item_id (e.g. ['id1', 'id2', 'id3']). "
            "Do not return any explanation, only the JSON list."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
            {
                "role": "assistant",
                "content": (
                    "Here are all the products from Mercari (in JSON):\n"
                    f"{json.dumps(search_results, ensure_ascii=False)}"
                ),
            },
        ]
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
        )
        message = response.choices[0].message.content
        try:
            topk_ids = json.loads(message)
        except Exception:
            topk_ids = []
        topk = []
        for pid in topk_ids:
            for item in search_results:
                if str(item.get("item_id")) == str(pid):
                    topk.append(item)
                    break
        return {
            "message": message,
            "products": topk,
        }
