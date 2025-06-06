import argparse
import urllib.parse
from dataclasses import dataclass
from typing import List, Optional

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
                    url=f"https://jp.mercari.com{href}" if href else None,
                    item_id=item_id,
                    itemtype=itemtype,
                )
            )
        except Exception as e:
            print(f"[Scraper] Error parsing product: {e}")
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
