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
    "description": "Search Mercari for products based on user criteria. Returns a list of product dicts.",
    "parameters": {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "Search keyword(s)"},
            # "excludeKeyword": {"type": "string", "description": "Exclude keyword(s)"},
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
            },
            # "status": {"type": "array", "items": {"type": "string"}},
            # "sizeId": {"type": "array", "items": {"type": "string"}},
            # "categoryId": {"type": "array", "items": {"type": "string"}},
            # "brandId": {"type": "array", "items": {"type": "string"}},
            # "sellerId": {"type": "array", "items": {"type": "string"}},
            # "priceMin": {"type": "integer"},
            # "priceMax": {"type": "integer"},
            # "itemConditionId": {"type": "array", "items": {"type": "string"}},
            # "shippingPayerId": {"type": "array", "items": {"type": "string"}},
            # "shippingFromArea": {"type": "array", "items": {"type": "string"}},
            # "shippingMethod": {"type": "array", "items": {"type": "string"}},
            # "colorId": {"type": "array", "items": {"type": "string"}},
            # "hasCoupon": {"type": "boolean"},
            # "createdAfterDate": {"type": "string"},
            # "createdBeforeDate": {"type": "string"},
            # "attributes": {"type": "array", "items": {"type": "string"}},
            # "itemTypes": {"type": "array", "items": {"type": "string"}},
            # "skuIds": {"type": "array", "items": {"type": "string"}},
            # "shopIds": {"type": "array", "items": {"type": "string"}},
            # "promotionValidAt": {"type": ["string", "null"]},
            # "excludeShippingMethodIds": {"type": "array", "items": {"type": "string"}},
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
        system_prompt = (
            "You are a helpful shopping assistant for Mercari Japan. "
            "You can use the 'mercari_search' tool to search for products based on user needs. "
            "You can also use the 'get_recommend_product' tool to select the top 3 recommended products from a list. "
            "After using the tools, summarize the recommendations in a Markdown table with columns: Name, Price, Reason, Link, Image. "
            "Be persuasive and user-friendly in your explanations."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
        tools = [mercari_search_tool, get_recommend_product_tool]
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
                print(function_name)
                print(call_id)
                print(args)
                if function_name == "mercari_search":
                    mercari_items = search_mercari(args.get("keyword", ""))
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
                elif function_name == "get_recommend_product":
                    products = args.get("products", [])
                    user_request = args.get("user_request", "")
                    top_products = self.recommend_products(
                        user_request, products, GPTModel.GPT_4_1_MINI
                    )
                    self.all_results["top3"] = top_products.get("products", [])
                    messages.append(output)
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
                    "raw_results": self.all_results.get("search_results", []),
                }

    def recommend_products(
        self, user_input: str, search_results: list, model: str
    ) -> dict:
        """
        Use LLM to recommend products based on user input and search results.
        """
        system_prompt = (
            "You are a helpful shopping assistant for Mercari Japan. "
            "You will receive a list of products from Mercari and a user's shopping request. "
            "For each product, provide a clear and concise reason for your recommendation, considering factors such as price, product condition, seller reputation, and keyword relevance. "
            "Present your recommendations in a Markdown table with the following columns: Name, Price, Reason, Link, Image. "
            "Be persuasive and user-friendly in your explanations."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
            {
                "role": "assistant",
                "content": (
                    "Here are the 3 selected products from Mercari (in JSON):\n"
                    f"{json.dumps(search_results, ensure_ascii=False)}"
                ),
            },
        ]
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
        )
        message = response.choices[0].message.content
        return {
            "message": message,
            "products": search_results,
        }
