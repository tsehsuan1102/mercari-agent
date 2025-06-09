import os
import json
from typing import Dict, Any
from dotenv import load_dotenv
from openai import OpenAI
from src.scraper.mercari_scraper import search_mercari
import re

load_dotenv()

GPT_MODEL = "gpt-4.1-mini"

# Mercari search tool schema for OpenAI function calling
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


def extract_top_products_from_message(message: str, search_results: list) -> list:
    # try to extract top products from LLM output
    # support markdown table or list
    top_products = []
    if not search_results:
        return []
    # find all product names
    names = [item["name"] for item in search_results]
    found_names = []
    # try to extract product names from markdown table or list
    for name in names:
        if name in message:
            found_names.append(name)
    # only take top 3
    for name in found_names[:3]:
        for item in search_results:
            if item["name"] == name:
                top_products.append(item)
                break
    # fallback: if not found, take top 3
    if not top_products:
        top_products = search_results[:3]
    return top_products


def agent_respond(user_input: str) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment.")
    client = OpenAI(api_key=api_key)

    system_prompt = (
        "You are a helpful shopping assistant for Mercari Japan. "
        "You can use the 'mercari_search' tool to search for products based on user needs. "
        "After getting the search results, analyze the products and select the top 3 that best match the user's needs. "
        "For each product, provide a clear and concise reason for your recommendation. "
        "Summarize the search results in a concise, short manner. "
        "Present the recommendations in a well-structured, easy-to-understand format, preferably as a Markdown table with columns: Name, Price, Reason, Link, Image. "
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input},
    ]
    tools = [mercari_search_tool]

    response = client.responses.create(model=GPT_MODEL, input=messages, tools=tools)

    if response.output and getattr(response.output[0], "type", None) == "function_call":
        function_name = getattr(response.output[0], "name", None)
        if function_name == "mercari_search":
            tool_call = response.output[0]
            args = json.loads(getattr(tool_call, "arguments", "{}"))
            # execute the tool
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
            # 直接用 LLM 產生推薦
            return recommend_products_llm(user_input, search_results, client, GPT_MODEL)
        else:
            return {
                "message": getattr(response.output[0], "content", ""),
                "products": [],
                "raw_results": [],
            }
    else:
        return {
            "message": getattr(response.output[0], "content", ""),
            "products": [],
            "raw_results": [],
        }


def recommend_products_llm(
    user_input: str, search_results: list, client, model: str
) -> dict:
    """
    用 LLM 根據用戶需求與商品清單，產生推薦理由與推薦商品
    """
    system_prompt = (
        "You are a helpful shopping assistant for Mercari Japan. "
        "You will receive a list of products from Mercari and a user's shopping request. "
        "Your job is to analyze the products and select the 3 best matches for the user's needs. "
        "For each recommended product, provide a clear and concise reason for your recommendation, considering factors such as price, product condition, seller reputation, and keyword relevance. "
        "Present your recommendations in a Markdown table with the following columns: Name, Price, Reason, Link, Image. "
        "Be persuasive and user-friendly in your explanations."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input},
        {
            "role": "assistant",
            "content": (
                "Here are the search results from Mercari (in JSON):\n"
                f"{json.dumps(search_results, ensure_ascii=False)}"
            ),
        },
    ]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7,
    )
    message = response.choices[0].message.content
    # 你可以用 extract_top_products_from_message 來抽出推薦商品
    products = extract_top_products_from_message(message, search_results)
    return {
        "message": message,
        "products": products,
        "raw_results": search_results,
    }
