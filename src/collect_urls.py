import argparse
import requests
from bs4 import BeautifulSoup
import time
import json
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Constants
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}
OUTPUT_FILE = "GPR_URLS/all_article_urls.jsonl"

def get_news_urls(keyword, date_str, page=1):
    """
    Fetches news URLs for a given keyword and date from Naver News Search.
    date_str format: YYYY.MM.DD
    """
    # ds, de = date_str, date_str (Daily search)
    start_idx = (page - 1) * 10 + 1
    url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sm=tab_opt&sort=0&photo=0&field=0&pd=3&ds={date_str}&de={date_str}&docid=&related=0&mynews=0&office_type=0&office_section_code=0&news_office_checked=&nso=so%3Ar%2Cp%3Afrom{date_str.replace('.','')}to{date_str.replace('.','')}&is_sug_officeid=0&start={start_idx}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        if response.status_code != 200:
            logger.warning(f"Status {response.status_code} for {date_str} p{page}")
            return [], False

        soup = BeautifulSoup(response.text, "html.parser")
        
        # Check for "No results"
        no_result = soup.select_one(".not_found02")
        if no_result:
            return [], False

        # Extract URLs
        articles = []
        # Naver news links usually have class "info" or direct title links
        # Specifically targeting "Naver News" button links (official Naver hosted)
        # Class usually `info` -> `a` text "네이버뉴스"
        
        # Selector for "Naver News" link: a.info (press_edit etc don't match exactly)
        # Better: Look for class="info" and text="네이버뉴스"
        info_links = soup.select("a.info")
        for link in info_links:
            if "네이버뉴스" in link.text and "news.naver.com" in link.get("href"):
                articles.append({
                    "url": link.get("href"),
                    "date": date_str,
                    "keyword": keyword
                })
        
        return articles, True
    except Exception as e:
        logger.error(f"Error fetching {date_str} p{page}: {e}")
        return [], False

def scan_date(date, keyword):
    """Scans all pages for a single date."""
    date_str = date.strftime("%Y.%m.%d")
    collected = []
    
    # Naver limits to 400 pages (4000 items) usually.
    # We stop if empty.
    max_pages = 400 
    
    # Heuristic: Check page 1. If empty, stop.
    # Check page 10, 20... exponential to find end? No, just linear is safer for coverage.
    # Or parallelize pages? No, Naver blocks aggressive parallel on same query.
    # Better: Linear scan for pages, but parallelize DATES.
    
    for page in range(1, max_pages + 1):
        urls, has_more = get_news_urls(keyword, date_str, page)
        if not urls and not has_more:
            break
            
        collected.extend(urls)
        
        # If less than 10 items found, it's likely the last page
        if len(urls) < 10:
            break
            
        time.sleep(0.1) # Polite delay
        
    return collected

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", type=str, default="국민연금")
    parser.add_argument("--start", type=str, default="2024.12.20")
    parser.add_argument("--end", type=str, default="2025.06.20")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    
    # Create Output Dir
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    # Generate Date Range
    start_date = datetime.strptime(args.start, "%Y.%m.%d")
    end_date = datetime.strptime(args.end, "%Y.%m.%d")
    delta = (end_date - start_date).days + 1
    dates = [start_date + timedelta(days=i) for i in range(delta)]
    
    logger.info(f"Target: {args.keyword}")
    logger.info(f"Range: {args.start} ~ {args.end} ({len(dates)} days)")
    logger.info(f"Workers: {args.workers}")
    
    total_count = 0
    
    # Load seen URLs
    seen = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    seen.add(json.loads(line)["url"])
                except:
                    pass
    logger.info(f"Loaded {len(seen)} existing URLs.")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_date = {executor.submit(scan_date, date, args.keyword): date for date in dates}
        
        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            for future in as_completed(future_to_date):
                date = future_to_date[future]
                try:
                    results = future.result()
                    new_items = 0
                    for item in results:
                        if item["url"] not in seen:
                            seen.add(item["url"])
                            f.write(json.dumps(item, ensure_ascii=False) + "\n")
                            new_items += 1
                            total_count += 1
                    
                    logger.info(f"Done {date.strftime('%Y-%m-%d')}: Found {len(results)} (New: {new_items})")
                    f.flush() # Secure write
                except Exception as e:
                    logger.error(f"Date {date} failed: {e}")
    
    logger.info(f"Completed. Total collected: {total_count}")

if __name__ == "__main__":
    main()
