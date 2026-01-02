import asyncio
import argparse
import json
import os
import sys
import logging
# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import List, Dict, Any

from playwright.async_api import async_playwright
import aiohttp

# Import project parsers
from src.parsers import parse_demographics, fetch_comments_api, extract_oid_aid, parse_article_details
# We need to mock or use config
from src.config import config

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/final_collection.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

INPUT_FILE = "GPR_URLS/stats_urls.jsonl"
OUTPUT_DIR = "GPR_FINAL"
ARTICLES_FILE = os.path.join(OUTPUT_DIR, f"final_articles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
COMMENTS_FILE = os.path.join(OUTPUT_DIR, f"final_comments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")

CONCURRENCY = 4

async def process_url(sem, context, http_session, line: str):
    async with sem:
        try:
            meta = json.loads(line)
            url = meta["url"]
            oid, aid = extract_oid_aid(url)
            
            logger.info(f"Processing: {url}")
            
            # Data container
            article_data = {
                "url": url,
                "oid": oid,
                "aid": aid,
                "title": "",
                "date": meta.get("date"),
                "keyword": meta.get("keyword"),
                "collected_at": datetime.now().isoformat(),
                "demographics": {},
                "stats_verification": "failed" # init
            }

            # 1. Playwright: Visit page for Demographics & Title
            page = await context.new_page()
            try:
                # Block heavy assets
                await page.route("**/*", lambda route: route.abort() 
                         if route.request.resource_type in ["image", "media", "font"] 
                         else route.continue_())

                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                
                # Scroll to ensure chart load
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.0) # Wait for animation
                
                # Parse Stats
                demog = await parse_demographics(page)
                article_data["demographics"] = demog
                
                if demog.get("demographic_available"):
                    article_data["stats_verification"] = "success"
                
                # Parse Details (Title etc)
                details = await parse_article_details(page, url)
                article_data["title"] = details.get("title", "")
                
            except Exception as e:
                logger.error(f"Playwright error for {url}: {e}")
                article_data["error_pw"] = str(e)
            finally:
                await page.close()
            
            # 2. API: Fetch Comments
            if oid and aid:
                try:
                    comments, social_meta = await fetch_comments_api(
                        oid, aid, 
                        max_comments=1000000, # Maximize collection
                        session=http_session,
                        stop_on_403=False
                    )
                    
                    article_data["comment_count_api"] = len(comments)
                    article_data["social_meta"] = social_meta # Store raw social info too
                    
                    # Save Comments
                    if comments:
                        save_comments(comments, url)
                        
                except Exception as e:
                    logger.error(f"API error for {url}: {e}")
                    article_data["error_api"] = str(e)
            
            # Save Article
            save_article(article_data)
            
        except Exception as e:
            logger.error(f"Critical Worker Error: {e}")

def save_article(data):
    with open(ARTICLES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

def save_comments(comments, url):
    with open(COMMENTS_FILE, "a", encoding="utf-8") as f:
        for c in comments:
            c["article_url"] = url
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Load targets
    urls = []
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    urls.append(line.strip())
    else:
        logger.error(f"Input file not found: {INPUT_FILE}")
        return

    logger.info(f"Targeting {len(urls)} URLs for final collection.")
    
    sem = asyncio.Semaphore(CONCURRENCY)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 ...") # User agent from config ideally
        
        async with aiohttp.ClientSession() as http_session:
            tasks = []
            for line in urls:
                tasks.append(asyncio.create_task(process_url(sem, context, http_session, line)))
                
            # Progress monitoring could be added here
            await asyncio.gather(*tasks)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
