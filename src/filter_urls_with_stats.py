import asyncio
import argparse
import json
import os
import logging
from typing import List, Set
from playwright.async_api import async_playwright, BrowserContext

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

INPUT_FILE = "GPR_URLS/all_article_urls.jsonl"
OUTPUT_FILE = "GPR_URLS/stats_urls.jsonl"
SEMAPHORE_LIMIT = 3

async def check_url_for_stats(context: BrowserContext, url: str) -> bool:
    page = await context.new_page()
    has_stats = False
    try:
        # Block resources to speed up
        await page.route("**/*", lambda route: route.abort() 
                         if route.request.resource_type in ["image", "media", "font"] 
                         else route.continue_())

        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # Scroll to bottom to trigger lazy loading of comments/stats
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1.0) # Wait for JS to render
        
        # Check for chart container
        # Selector from src/selectors.py: DemographicSelectors.CHART_AREA = "div.u_cbox_chart_cont"
        # Sometimes need to scroll specifically to comment area?
        # Let's try to wait for it briefly
        try:
            await page.locator("div.u_cbox_chart_cont").wait_for(state="visible", timeout=2000)
            has_stats = True
        except:
            # Last ditch: check if element exists even if not fully visible/animated
            if await page.locator("div.u_cbox_chart_cont").count() > 0:
                 has_stats = True
            
    except Exception as e:
        logger.debug(f"Error checking {url}: {e}")
    finally:
        await page.close()
        
    return has_stats

async def worker(sem, context, queue, stats_file):
    while not queue.empty():
        line = await queue.get()
        try:
            data = json.loads(line)
            url = data["url"]
            
            async with sem:
                has_stats = await check_url_for_stats(context, url)
                
            if has_stats:
                logger.info(f"[MATCH] Stats found: {url}")
                async with stats_file_lock: # Minimal locking manual approach or just use append
                     # In asyncio single threaded loop, append is safe usually? 
                     # Actually standard file I/O is blocking.
                     # But for this simple script, we can just append.
                     with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                         f.write(json.dumps(data, ensure_ascii=False) + "\n")
            else:
                # logger.info(f"[SKIP] No stats: {url}")
                print(".", end="", flush=True) # Progress dot
                
        except Exception as e:
            logger.error(f"Worker error: {e}")
        finally:
            queue.task_done()

# Global lock for file writing in case we expand to threads (though asyncio is single threaded)
stats_file_lock = asyncio.Lock()

async def main():
    # Load URLs
    urls = []
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    urls.append(line.strip())
    
    logger.info(f"Loaded {len(urls)} URLs to check.")
    
    # Init output
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    # Don't overwrite if existing? Optional. User wants to filter. 
    # Let's overwrite to start fresh or append?
    # Let's clear it first to avoid duplicates from previous failed runs.
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        pass
        
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        
        queue = asyncio.Queue()
        for u in urls:
            queue.put_nowait(u)
            
        sem = asyncio.Semaphore(SEMAPHORE_LIMIT)
        
        tasks = []
        for _ in range(SEMAPHORE_LIMIT):
            tasks.append(asyncio.create_task(worker(sem, context, queue, OUTPUT_FILE)))
            
        await queue.join()
        
        for task in tasks:
            task.cancel()
            
        await browser.close()
        
    logger.info("Filtering Complete.")

if __name__ == "__main__":
    asyncio.run(main())
