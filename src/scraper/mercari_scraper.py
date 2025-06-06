import argparse
import urllib.parse
from dataclasses import dataclass
from typing import List, Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://jp.mercari.com/search?keyword="


@dataclass
class MercariItem:
    name: str
    price: str
    image: Optional[str] = None
    url: Optional[str] = None
    item_id: Optional[str] = None
    itemtype: Optional[str] = None


def search_mercari(query: str) -> List[MercariItem]:
    print(f"[Scraper] Searching Mercari for: {query}")
    encoded_query = urllib.parse.quote(query)
    url = BASE_URL + encoded_query
    print(f"[Scraper] URL: {url}")

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)

    driver.get(url)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'a[data-testid="thumbnail-link"]')
            )
        )
    except Exception as e:
        print("[Scraper] Timeout waiting for product links:", e)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    product_links = soup.select('a[data-testid="thumbnail-link"]')
    print(f"[Scraper] Found {len(product_links)} product links.")

    items = []
    for link in product_links:
        thumbnail_div = link.find("div", class_="merItemThumbnail")
        if thumbnail_div and thumbnail_div.has_attr("aria-label"):
            label = thumbnail_div["aria-label"]
            if "の画像" in label:
                name, price = label.split("の画像", 1)
                name = name.strip()
                price = price.strip()
            else:
                name = label.strip()
                price = "N/A"
            item_id = thumbnail_div.get("id")
            itemtype = thumbnail_div.get("itemtype")
        else:
            name = "N/A"
            price = "N/A"
            item_id = None
            itemtype = None
        image_url = None
        figure = thumbnail_div.find("figure") if thumbnail_div else None
        if figure:
            img_tag = figure.find("img")
            if img_tag and img_tag.has_attr("src"):
                image_url = img_tag["src"]
        href = link.get("href")
        item = MercariItem(
            name=name,
            price=price,
            image=image_url,
            url=f"https://jp.mercari.com{href}" if href else None,
            item_id=item_id,
            itemtype=itemtype,
        )
        items.append(item)
    driver.quit()
    print(f"[Scraper] Found {len(items)} items for query '{query}'.")
    return items


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mercari scraper")
    parser.add_argument(
        "keyword", help="Search keyword, e.g. python mercari_scraper.py Knife", type=str
    )
    args = parser.parse_args()
    items = search_mercari(args.keyword)
    print(items)
