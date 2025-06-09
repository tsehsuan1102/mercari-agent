import argparse
import urllib.parse
from dataclasses import dataclass
from typing import List, Optional, Any, Dict

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://jp.mercari.com/search?keyword="


# --- type defs ---
@dataclass
class MercariItem:
    name: str
    price: str
    image: Optional[str] = None
    url: Optional[str] = None
    item_id: Optional[str] = None
    itemtype: Optional[str] = None


@dataclass
class MercariItemDetail(MercariItem):
    description: Optional[str] = None
    item_condition: Optional[str] = None
    categories: Optional[list] = None
    images: Optional[list] = None
    seller_name: Optional[str] = None
    seller_rating_count: Optional[str] = None
    seller_rating: Optional[str] = None


@dataclass
class MercariFilter:
    keyword: str = ""
    excludeKeyword: str = ""
    sort: str = "SORT_SCORE"
    order: str = "ORDER_DESC"
    status: list = None
    sizeId: list = None
    categoryId: list = None
    brandId: list = None
    sellerId: list = None
    priceMin: int = 0
    priceMax: int = 0
    itemConditionId: list = None
    shippingPayerId: list = None
    shippingFromArea: list = None
    shippingMethod: list = None
    colorId: list = None
    hasCoupon: bool = False
    createdAfterDate: str = "0"
    createdBeforeDate: str = "0"
    attributes: list = None
    itemTypes: list = None
    skuIds: list = None
    shopIds: list = None
    promotionValidAt: Any = None
    excludeShippingMethodIds: list = None

    def to_dict(self) -> Dict:
        return {
            "keyword": self.keyword,
            "excludeKeyword": self.excludeKeyword,
            "sort": self.sort,
            "order": self.order,
            "status": self.status or [],
            "sizeId": self.sizeId or [],
            "categoryId": self.categoryId or [],
            "brandId": self.brandId or [],
            "sellerId": self.sellerId or [],
            "priceMin": self.priceMin,
            "priceMax": self.priceMax,
            "itemConditionId": self.itemConditionId or [],
            "shippingPayerId": self.shippingPayerId or [],
            "shippingFromArea": self.shippingFromArea or [],
            "shippingMethod": self.shippingMethod or [],
            "colorId": self.colorId or [],
            "hasCoupon": self.hasCoupon,
            "createdAfterDate": self.createdAfterDate,
            "createdBeforeDate": self.createdBeforeDate,
            "attributes": self.attributes or [],
            "itemTypes": self.itemTypes or [],
            "skuIds": self.skuIds or [],
            "shopIds": self.shopIds or [],
            "promotionValidAt": self.promotionValidAt,
            "excludeShippingMethodIds": self.excludeShippingMethodIds or [],
        }


# --- functions ---
def get_filters(driver):
    filters = []
    try:
        # Get filter section
        filter_section = driver.find_element(By.ID, "search-filter")
        # Get all li[data-testid] filter conditions
        filter_lis = filter_section.find_elements(By.CSS_SELECTOR, "li[data-testid]")
        for li in filter_lis:
            filter_info = {}
            data_testid = li.get_attribute("data-testid")
            filter_info["data-testid"] = data_testid

            # Get title (use data-testid="filter-heading" or li button span)
            try:
                title_btn = li.find_element(By.TAG_NAME, "button")
                title_span = title_btn.find_element(By.TAG_NAME, "span")
                filter_info["title"] = title_span.text.strip()
            except Exception:
                filter_info["title"] = data_testid

            # Check for select (dropdown)
            try:
                select = li.find_element(By.TAG_NAME, "select")
                options = []
                for opt in select.find_elements(By.TAG_NAME, "option"):
                    options.append(
                        {"value": opt.get_attribute("value"), "label": opt.text.strip()}
                    )
                filter_info["type"] = "select"
                filter_info["options"] = options
            except Exception:
                pass

            # Check for checkboxes (input[type="checkbox"])
            checkboxes = li.find_elements(By.CSS_SELECTOR, 'input[type="checkbox"]')
            if checkboxes:
                options = []
                for cb in checkboxes:
                    # label is in the next span
                    try:
                        label = cb.find_element(
                            By.XPATH, "following-sibling::div//span"
                        )
                        label_text = label.text.strip()
                    except Exception:
                        label_text = ""
                    options.append(
                        {
                            "value": cb.get_attribute("value"),
                            "label": label_text,
                            "name": cb.get_attribute("name"),
                        }
                    )
                filter_info["type"] = "checkbox"
                filter_info["options"] = options

            # Check for number input (price)
            price_inputs = li.find_elements(By.CSS_SELECTOR, 'input[type="number"]')
            if price_inputs:
                filter_info["type"] = "price"
                filter_info["inputs"] = [
                    {
                        "name": inp.get_attribute("name"),
                        "placeholder": inp.get_attribute("placeholder"),
                        "min": inp.get_attribute("min"),
                        "max": inp.get_attribute("max"),
                    }
                    for inp in price_inputs
                ]

            # Check for text input (brand, exclude keyword)
            text_inputs = li.find_elements(By.CSS_SELECTOR, 'input[type="text"]')
            if text_inputs:
                filter_info["type"] = "text"
                filter_info["inputs"] = [
                    {
                        "name": inp.get_attribute("name"),
                        "placeholder": inp.get_attribute("placeholder"),
                    }
                    for inp in text_inputs
                ]

            filters.append(filter_info)
    except Exception as e:
        print("[Scraper] Error parsing filters:", e)
    return filters


def build_search_url(filters: dict) -> str:
    base_url = "https://jp.mercari.com/search"
    params = {}
    if filters.get("keyword"):
        params["keyword"] = filters["keyword"]
    if filters.get("categoryId"):
        params["category_id"] = filters["categoryId"][0]
    if filters.get("priceMin"):
        params["price_min"] = filters["priceMin"]
    if filters.get("priceMax"):
        params["price_max"] = filters["priceMax"]
    if filters.get("itemConditionId"):
        params["item_condition_id"] = ",".join(filters["itemConditionId"])
    if filters.get("sort"):
        sort_map = {
            "SORT_CREATED_TIME": "created_time",
            "SORT_SCORE": "score",
            "SORT_PRICE": "price",
            "SORT_NUM_LIKES": "num_likes",
        }
        sort_val = sort_map.get(filters["sort"], None)
        if sort_val:
            params["sort"] = sort_val
    if filters.get("order"):
        order_map = {"ORDER_DESC": "desc", "ORDER_ASC": "asc"}
        order_val = order_map.get(filters["order"], None)
        if order_val:
            params["order"] = order_val
    query = urllib.parse.urlencode(params, doseq=True)
    return f"{base_url}?{query}"


def search_mercari(filters: dict, limit: int = 20) -> List[MercariItem]:
    print(f"[Scraper] Searching Mercari with filters: {filters}")
    url = build_search_url(filters)
    print(f"[Scraper] URL: {url}")

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)

    driver.get(url)
    # filters_info = get_filters(driver)
    # print("[Scraper] Filters:")
    # import json
    # print(json.dumps(filters_info, ensure_ascii=False, indent=2))
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'a[data-testid="thumbnail-link"]')
            )
        )
    except Exception as e:
        print("[Scraper] Timeout waiting for product links:", e)

    product_links = driver.find_elements(
        By.CSS_SELECTOR, 'a[data-testid="thumbnail-link"]'
    )
    print(f"[Scraper] Found {len(product_links)} product links.")

    items = []
    for link in product_links:
        try:
            thumbnail_div = link.find_element(By.CLASS_NAME, "merItemThumbnail")
            label = thumbnail_div.get_attribute("aria-label")
            if label and "の画像" in label:
                name, price = label.split("の画像", 1)
                name = name.strip()
                price = price.strip()
            elif label:
                name = label.strip()
                price = "N/A"
            else:
                name = "N/A"
                price = "N/A"
            item_id = thumbnail_div.get_attribute("id")
            itemtype = thumbnail_div.get_attribute("itemtype")
            # get image url
            image_url = None
            try:
                img_tag = thumbnail_div.find_element(By.TAG_NAME, "img")
                image_url = img_tag.get_attribute("src")
            except Exception:
                pass
            href = link.get_attribute("href")
            items.append(
                MercariItem(
                    name=name,
                    price=price,
                    image=image_url,
                    url=href if href else None,
                    item_id=item_id,
                    itemtype=itemtype,
                )
            )
        except Exception as e:
            print(f"[Scraper] Error parsing product: {e}")
    driver.quit()
    print(
        f"[Scraper] Found {len(items)} items for query '{filters.get('keyword', '')}'."
    )
    return items[:limit]


def scrape_mercari_item(item: MercariItem) -> MercariItemDetail:
    """
    Scrape detailed info from a single Mercari item page.
    Args:
        url (str): The URL of the Mercari item.
    Returns:
        dict: Detailed item info.
    """

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)

    driver.get(item.url)
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="name"] h1'))
        )
    except Exception as e:
        print("[Scraper] Timeout waiting for item detail:", e)
    result = {}

    try:
        name_elem = driver.find_element(By.CSS_SELECTOR, '[data-testid="name"] h1')
        result["name"] = name_elem.text.strip()
    except Exception:
        result["name"] = None

    try:
        price_elem = driver.find_element(By.CSS_SELECTOR, '[data-testid="price"]')
        result["price"] = price_elem.text.strip()
    except Exception:
        result["price"] = None

    try:
        desc_elem = driver.find_element(By.CSS_SELECTOR, '[data-testid="description"]')
        result["description"] = desc_elem.text.strip()
    except Exception:
        result["description"] = None

    try:
        status_elem = driver.find_element(By.CSS_SELECTOR, '[data-testid="商品の状態"]')
        result["item_condition"] = status_elem.text.strip()
    except Exception:
        result["item_condition"] = None

    try:
        category_elems = driver.find_elements(
            By.CSS_SELECTOR, '[data-testid="item-detail-category"] a'
        )
        result["categories"] = [a.text.strip() for a in category_elems]
    except Exception:
        result["categories"] = []

    try:
        image_elems = driver.find_elements(
            By.CSS_SELECTOR, '[data-testid^="image-"] img'
        )
        result["images"] = [
            img.get_attribute("src") for img in image_elems if img.get_attribute("src")
        ]
    except Exception:
        result["images"] = []

    try:
        seller_elem = driver.find_element(
            By.CSS_SELECTOR, '[data-testid="seller-link"] .content__a9529387 p'
        )
        result["seller_name"] = seller_elem.text.strip()
        rating_elem = driver.find_element(
            By.CSS_SELECTOR, '[data-testid="seller-link"] .count__60fe6cce'
        )
        result["seller_rating_count"] = rating_elem.text.strip()
        star_elem = driver.find_element(
            By.CSS_SELECTOR, '[data-testid="seller-link"] .merRating'
        )
        result["seller_rating"] = star_elem.get_attribute("aria-label")
    except Exception:
        result["seller_name"] = None
        result["seller_rating_count"] = None
        result["seller_rating"] = None

    driver.quit()
    return MercariItemDetail(
        name=result.get("name"),
        price=result.get("price"),
        image=item.image,
        url=item.url,
        item_id=item.item_id,
        itemtype=item.itemtype,
        description=result.get("description"),
        item_condition=result.get("item_condition"),
        categories=result.get("categories"),
        images=result.get("images"),
        seller_name=result.get("seller_name"),
        seller_rating_count=result.get("seller_rating_count"),
        seller_rating=result.get("seller_rating"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mercari scraper")
    parser.add_argument(
        "keyword", help="Search keyword, e.g. python mercari_scraper.py Knife", type=str
    )
    args = parser.parse_args()
    items = search_mercari(args.keyword)
    print(items)
