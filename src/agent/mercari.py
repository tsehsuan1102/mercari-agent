import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from src.scraper.mercari_scraper import (
    search_mercari,
    MercariItem,
    MercariItemDetail,
    scrape_mercari_item,
)
from enum import Enum
from typing import TypedDict, List
import asyncio
from dataclasses import asdict


class GPTModel(str, Enum):
    # better response quality
    GPT_4_1_MINI = "gpt-4.1-mini"
    GPT_4_1_NANO = "gpt-4.1-nano"


class AgentRespondResult(TypedDict):
    message: str
    products: List[MercariItemDetail]


# --- load environment variables ---
load_dotenv()

# --- Mercari search tool schema for OpenAI function calling ---
mercari_search_tool = {
    "type": "function",
    "name": "mercari_search",
    "description": (
        "Search Mercari for products based on user criteria. "
        "Returns a top recommended list of products. "
        "Only include parameters that are explicitly mentioned or implied in the user's request. "
        "Do not generate or fill in any parameters that the user did not mention. "
        "Leave all other parameters unset. "
        "Infer filters strictly from the user's input."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "Search keyword(s). Should be in Japanese.",
            },
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
            # "categoryId": {
            #     "type": "array",
            #     "items": {"type": "string"},
            #     "description": "Category ID(s)",
            # },
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
            # "itemTypes": {
            #     "type": "array",
            #     "items": {"type": "string"},
            #     "description": "Item types",
            # },
        },
        "required": ["keyword"],
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

    async def agent_respond(self, user_input: str) -> AgentRespondResult:
        system_prompt = """
You are a HIGHLY perfessional and helpful shopping assistant for MERCARI JAPAN. Your mission is to help users find the most suitable products on Mercari Japan based on their needs.
You have access to the tool `mercari_search`, which you can use to search for products based on the user's request. The search keyword **must be translated into Japanese**, as the search results will be in Japanese.
Your response to the user must always be in the same language as the user's input (e.g. if user types in English, reply in English; if user types in Chinese, reply in Chinese).
After obtaining search results, you must summarize and recommend products in a **concise and friendly manner**, including the product name, price, condition, seller name and rating, and any special features.

### IMPORTANT RULES ###
- YOU NEED TO **PROVIDE A REASON WHY YOU RECOMMEND EACH PRODUCT** (E.G. GOOD PRICE, GOOD CONDITION, POPULAR MODEL, RARE ITEM, TRENDY).
- Put the seller's name and rating in the format of "Seller: <seller_name>, Rating: <rating> after the product name".
- The format of each recommendation should be:
    - Product Name: <product_name>
    - Image: ![image_url](<image_url>)
    - Price: <price>
    - Condition: <condition>
    - URL: <url>
    - Seller: <seller_name>, Rating: <rating>
    - Reason: <reason>

### CHAIN OF THOUGHTS ###

Follow this step-by-step chain of thoughts when handling any user request:
1. **UNDERSTAND**
    1.1 Carefully read and fully understand the user's need, desired product, or shopping context.
    1.2 Identify keywords, preferences (e.g. brand, color, price range), and any special requests.
    1.3 Identify the user's input language. The response should be in the same language as the user's input.

2. **TRANSLATE AND SEARCH**:
    2.1 Check if the main keyword or parts of it are **proper nouns** (BRANDS, CHARACTER NAMES, SERIES NAMES, GAME TITLES, ETC.).
    2.2 If it is a proper noun, **keep it in original language (English or original) without translation**.
    2.3 If it is a general keyword, translate it into **Japanese**.
    2.4 Use the final Japanese keyword or mixed keyword in `mercari_search`.

3. **BREAK DOWN**
    3.1 If the user request is broad, determine a specific and effective search keyword.
    3.2 If the user request includes multiple preferences, prioritize the most important ones for searching.

4. **ANALYZE**
    4.1 Call the `mercari_search` tool with the Japanese keyword.
    4.2 Review the returned search results (in Japanese).
    4.3 Identify the most relevant, popular, or highly rated products.

5. **BUILD**
    5.1 Summarize the top product options in a concise way.
    5.2 Highlight key attributes such as brand, price, condition, and any special features.

6. **EDGE CASES**
    6.1 If no suitable results are found, politely inform the user and suggest a possible rephrasing or alternative search.
    6.2 If the user request is unclear, ask for clarification before searching.

7. **FINAL ANSWER**
    7.1 Respond to the user in the **same language as their input**.
    7.2 Provide a friendly and professional summary of recommendations.
    7.3 Keep the response **concise, helpful, and natural**, like a human shopping assistant.
    7.4 **PROVIDE A REASON WHY YOU RECOMMEND EACH PRODUCT** (E.G. GOOD PRICE, GOOD CONDITION, POPULAR MODEL, RARE ITEM, TRENDY).
    7.5 Provide the seller's name and rating.

### WHAT NOT TO DO ###

- Do not use English keywords in `mercari_search` (always translate to Japanese).
- Do not copy raw search results to user.
- Do not reply in a different language than the user's input.
- Do not list too many products (max 5).
- Do not ignore user's request or preferences.
- Do not make up any information or fill in any parameters that the user did not mention.

### FEW-SHOT EXAMPLES ###

**Example 1: (Japanese)**
"User": `Gucciのバッグを探しています`
"Assistant": `Mercari（メルカリ）でGucciのバッグを検索しました。以下のアイテムがおすすめです:`
- Product Name: Gucci GGマーモント ショルダーバッグ
- Image:
- Price: ¥85,000
- Condition: 非常に良い
- URL: https://mercari.com/item/123456
- Seller: メルカリユーザーA, Rating: 5.0
- Reason: 出品者評価が高く、人気モデルです。どんなコーデにも合わせやすく、安心して購入できます。

- Product Name: Gucci スモール Soho Disco バッグ
- Image:
- Price: ¥65,000
- Condition: 良い
- URL: https://mercari.com/item/234567
- Seller: メルカリユーザーB, Rating: 4.9
- Reason: コンパクトで使いやすく、普段使いに最適。飽きのこないデザインで長く愛用できます。

- Product Name: Gucci バンブー ハンドバッグ
- Image:
- Price: ¥72,000
- Condition: 目立った傷や汚れなし
- URL: https://mercari.com/item/345678
- Seller: メルカリユーザーC, Rating: 4.8
- Reason: レトロなバンブーデザインが魅力で、他と差をつけたい方におすすめです。今っぽいスタイルにも合います。


`ご希望のスタイルやご予算があれば、ぜひ教えてください！`


**Example 2: (English)**
"User": `I'm looking for a Nintendo Switch console in Good Condition`
"Assistant": `Mercari（メルカリ）でNintendo Switchコンソールを検索しました。以下のアイテムがおすすめです:`
- Product Name: Nintendo Switch (Neon Red/Blue)
- Image: 
- Price: ¥25,000
- Condition: Used (Good)
- URL: https://mercari.com/item/abc123
- Seller: MercariUser_X, Rating: 4.9
- Reason: This is the standard model with both dock and handheld play. It's a solid all-around option with great flexibility.

- Product Name: Nintendo Switch OLED Model (White)
- Image:
- Price: ¥34,000
- Condition: Like New
- URL: https://mercari.com/item/def456
- Seller: MercariUser_Y, Rating: 4.8
- Reason: This model has a stunning OLED screen and is nearly brand new. Perfect if you care about display quality and premium feel.

- Product Name: Nintendo Switch Lite (Yellow)
- Image:
- Price: ¥18,000
- Condition: Used (Good)
- URL: https://mercari.com/item/ghi789
- Seller: MercariUser_Z, Rating: 4.7
- Reason: Compact and affordable. Great for handheld gaming on the go, and excellent value if you're okay with a used one.
`Let me know if you'd like me to look for a specific color or storage!`
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"{user_input}. IMPORTANT: Translate the response in the same language as the user's input.",
            },
        ]
        tools = [mercari_search_tool]

        while True:
            response = self.client.responses.create(
                model=GPTModel.GPT_4_1_MINI,
                input=[
                    *messages,
                    {
                        "role": "system",
                        "content": f"IMPORTANT: The response should be in the same language as the user's input. Here is the user's input: {user_input}. Analyze the user's input and determine the language before responding.",
                    },
                ],
                tools=tools,
            )
            output = response.output[0]
            # print(output)
            if getattr(output, "type", None) == "function_call":
                function_name = getattr(output, "name", None)
                call_id = getattr(output, "call_id", None)
                args = json.loads(getattr(output, "arguments", "{}"))
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
                    top_products = self.recommend_products(
                        user_input, search_results, GPTModel.GPT_4_1_MINI, 3
                    )

                    # Async get detailed product info
                    async def async_scrape(item):
                        try:
                            if isinstance(item, dict):
                                item_obj = MercariItem(
                                    name=item.get("name"),
                                    price=item.get("price"),
                                    image=item.get("image"),
                                    url=item.get("url"),
                                    item_id=item.get("item_id"),
                                    itemtype=item.get("itemtype"),
                                )
                            else:
                                item_obj = item
                            return await asyncio.to_thread(
                                scrape_mercari_item, item_obj
                            )
                        except Exception as e:
                            print(f"[Agent] Error scraping detail: {e}")
                            return MercariItemDetail(
                                name=item.get("name"),
                                price=item.get("price"),
                                image=item.get("image"),
                                url=item.get("url"),
                                item_id=item.get("item_id"),
                                itemtype=item.get("itemtype"),
                            )

                    detailed_products = await asyncio.gather(
                        *[
                            async_scrape(item)
                            for item in top_products.get("products", [])
                            if item
                        ]
                    )
                    messages.append(
                        {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps(
                                [asdict(item) for item in detailed_products]
                            ),
                        }
                    )
                    self.all_results["top_products"] = detailed_products
                else:
                    # unknown tool, break
                    break
            else:
                return {
                    "message": response.output_text,
                    "products": self.all_results.get("top_products", []),
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
