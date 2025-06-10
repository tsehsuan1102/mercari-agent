# Mercari Japan AI Shopping Agent

## Overview

This project is a Python-based AI agent that helps users search for products on Mercari Japan and recommends the top 3 items with clear reasoning.
The agent leverages OpenAI's function calling to interpret user intent, generates Japanese search keywords, scrapes product data using Selenium, and outputs user-friendly recommendations.

---

## Setup Instructions

### 1. Install Dependencies

Ensure you have **Python 3.10 or later** installed.

```bash
pip install -r requirements.txt
```

### 2. Set Up OpenAI API Key

Create a `.env` file in the project root directory:

```
OPENAI_API_KEY=your_openai_api_key (sk-xxx)
```

> **Note:** The API key is not included in this repository. I chose OpenAI because I already use it elsewhere and wanted to avoid recharging another provider for this project.

---

## Usage Instructions

### 1. Unzip and Enter the Project Directory

If you received a ZIP file, unzip it and enter the project folder:

```bash
unzip tsehsuan-mercari-agent.zip
cd mercari-agent
```

### 2. Run the Agent

```bash
python main.py
```

You will see:

```
Mercari Agent Test Mode: Please input your request:
User:
```

Type your shopping request in any language you prefer. For example:

```
User: Looking for a used iPhone under 20000 yen
```

The agent will search, recommend the top 3 products, and provide concise reasons and product details.

![Looking for a used iPhone](https://i.imgur.com/dzTyeyA.png)

### 3. Output Format

- The response language matches your input language.
- Product info includes name, price, condition, image, seller name and rating, and the reason for the recommendation.
- The agent's output is a Python dictionary with the following structure:

```python
{
    "message": str,  # A concise, user-friendly summary and recommendations (in the user's language)
    "products": List[MercariItemDetail]  # A list of dataclass objects with full product details
}
```

- **message**: A natural-language summary and recommendations, ready to display directly to the user.
- **products**: A list of `MercariItemDetail` objects, each containing all available product information (name, price, description, images, seller info, etc.).

**Why this design?**

- **Frontend Flexibility**: By providing both a ready-to-display message and a structured list of product details, frontend developers can:
  - Directly show the summary, or
  - Use the detailed product data to build custom UI components, enable further user interactions (e.g., "view more", "save", "compare"), or trigger additional actions.
- **Rich Interactivity**: The full product details make it easy to support features like product previews, deep links, or even follow-up questions about a specific item.

---

## Design Choices

1. **Selenium for Scraping**
   - Mercari's product data is rendered via JavaScript, so requests/BeautifulSoup cannot fetch results directly.
   - Initially, I attempted to access their API endpoints directly for testing purposes without formal integration. However, the endpoints require a valid session ID, and handling the authentication manually proved to be non-trivial. As a result, I opted to proceed with Selenium to simulate user interactions.
   - Selenium reliably extracts all required product details from the rendered frontend.

2. **LLM Function Calling**
   - OpenAI function calling is used to strictly infer search filters from explicit user input.
   - Keywords are automatically translated to Japanese for more accurate search results.

3. **Recommendation Flow**
   - The LLM selects the top 3 products based on the item details from the result page, then the agent scrapes each detail page for richer info (description, seller rating, etc.).

4. **Stateless Design**
   - The agent is currently stateless. In the future, session/context support could enable multi-turn conversations.

5. **Multilingual Support**
   - Input and output languages are automatically matched.

6. **Model Selection**
   - The current model used is **OpenAI GPT-4.1-mini**.
     - I compared GPT-4.1, GPT-4.1-mini, and GPT-4.1-nano using OpenAI Quick Evaluation on several test cases. GPT-4.1-mini demonstrated sufficiently stable and accurate performance for this use case.
     - Due to cost and response time considerations, I chose not to use the full GPT-4.1 model.

---

## Potential Improvements

- **Stateful & Multi-turn Dialogue**: Enable the agent to remember user preferences, shopping history, and context across multiple turns, allowing for more natural, conversational, and personalized shopping experiences.

- **User & Seller Profile Matching**: Incorporate user profiles (e.g., style, brand preferences, past purchases) and seller reputation/history to provide smarter, trust-aware recommendations.

- **Multimodal Input**: Support image, video, or voice input, allowing users to search by uploading a photo of an item, describing it verbally, or even sharing a video.

- **Serendipitous & Randomized Recommendations**: Occasionally suggest interesting or trending items outside the user's strict criteria, based on past user interactions or popular products, to encourage discovery and delight.

- **Advanced Filtering & Faceted Search**: Allow users to refine results with advanced filters (e.g., color, size, shipping options) and dynamically update recommendations.

- **Automated Bargain Alerts & Price Tracking**: Notify users when prices drop or when similar items are listed, leveraging historical price data and user watchlists.


---

## Notes

1. The scraper returns dataclass objects for easy downstream processing.
2. Selenium is used instead of requests due to Mercari's JS-rendered content.
3. OpenAI function calling enables rapid prototyping and evaluation.

---



