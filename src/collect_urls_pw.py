import asyncio
import argparse
import json
import os
import logging
from datetime import datetime, timedelta
from typing import List, Set
from playwright.async_api import async_playwright, Page, BrowserContext

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_FILE = "GPR_URLS/all_article_urls.jsonl"
SEMAPHORE_LIMIT = 3  # Reduced from 5 for stability

async def fetch_urls_for_date(context: BrowserContext, keyword: str, date_str: str, seen_urls: Set[str]):
    page = await context.new_page()
    collected_count = 0
    try:
        # Naver Advanced Search URL (Daily)
        # pd=3 (custom period), ds=date, de=date
        # sort=0 (relevance) or 1? Let's use Relevance (0) since we are bounded by date anyway.
        # Actually, using 'Latest' (1) is safer for pagination consistency?
        # Let's stick to sort=0 (Relevance) inside a single day, or 1 (Latest).
        
        base_url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sm=tab_opt&sort=1&photo=0&field=0&pd=3&ds={date_str}&de={date_str}"
        
        current_page = 1
        max_pages_per_day = 400 # Theoretical max
        
        while current_page <= max_pages_per_day:
            start_index = (current_page - 1) * 10 + 1
            url = f"{base_url}&start={start_index}"
            
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception as e:
                logger.warning(f"Timeout/Error on {date_str} p{current_page}: {e}")
                # Retry once?
                await asyncio.sleep(2)
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                except:
                    break

            # Check for "No results"
            no_result = await page.query_selector(".not_found02")
            if no_result:
                # logger.info(f"[{date_str}] 'No results' element found.")
                break
                
            # Extract URLs - Robust Method
            # Use Playwright's locator to find 'a' tags containing '네이버뉴스' text
            new_urls = await page.locator("a", has_text="네이버뉴스").evaluate_all("els => els.map(e => e.href)")
            
            # Filter to ensure they look like news links (optional, but safer)
            new_urls = [u for u in new_urls if "news.naver.com" in u or "entertain.naver.com" in u or "sports.news.naver.com" in u]
            
            # logger.info(f"[{date_str}] Page {current_page}: Found {len(new_urls)} URLs keys")
            
            if not new_urls:
                # Debug HTML
                content = await page.content()
                if "서비스를 이용할 수 없습니다" in content:
                     logger.error("Naver Blocked (CAPTCHA/Limit).")
                     await asyncio.sleep(10)
                break
                
            # Write immediately to file (locking needed? standard open 'a' is atomic enough for lines usually, but async...)
            # We'll just append to a list and return, or write to a shared queue?
            # Creating a critical section for file write might be safer, or just use one file handle in main.
            # For simplicity, let's return list chunk.
            
            batch_new = 0
            lines_to_write = []
            for u in new_urls:
                if u not in seen_urls:
                    seen_urls.add(u)
                    meta = {
                        "url": u,
                        "date": date_str,
                        "keyword": keyword,
                        "collected_at": datetime.now().isoformat()
                    }
                    lines_to_write.append(json.dumps(meta, ensure_ascii=False))
                    batch_new += 1
            
            if lines_to_write:
                # Append to file
                with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                    f.write("\n".join(lines_to_write) + "\n")
            
            collected_count += batch_new
            
            # Next page check
            # If we found less than 10 links, it's the last page
            if len(new_urls) < 10:
                break
                
            current_page += 1
            # Random sleep to be nice
            await asyncio.sleep(1.5)
            
    except Exception as e:
        logger.error(f"Error processing {date_str}: {e}")
    finally:
        await page.close()
        
    if collected_count > 0:
        logger.info(f"[{date_str}] Collected {collected_count} URLs")
    return collected_count

async def worker(sem, context, keyword, date_queue, seen_urls):
    total_collected = 0
    while not date_queue.empty():
        date_str = await date_queue.get()
        async with sem:
            count = await fetch_urls_for_date(context, keyword, date_str, seen_urls)
            total_collected += count
        date_queue.task_done()
    return total_collected

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", type=str, default="국민연금")
    parser.add_argument("--start", type=str, default="2024.12.20")
    parser.add_argument("--end", type=str, default="2025.06.20")
    parser.add_argument("--headless", action="store_true", default=True) # Default headless
    args = parser.parse_args()

    # Ensure output dir
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    # Generate dates
    start_date = datetime.strptime(args.start, "%Y.%m.%d")
    end_date = datetime.strptime(args.end, "%Y.%m.%d")
    date_list = []
    curr = start_date
    while curr <= end_date:
        date_list.append(curr.strftime("%Y.%m.%d"))
        curr += timedelta(days=1)
        
    logger.info(f"Target: {args.keyword}")
    logger.info(f"Range: {args.start} ~ {args.end} ({len(date_list)} days)")
    
    # Load seen
    seen_urls = set()
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            seen_urls.add(json.loads(line)["url"])
                        except: pass
        except: pass
    logger.info(f"Loaded {len(seen_urls)} existing URLs.")

    # Playwright Setup
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=args.headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        
        queue = asyncio.Queue()
        for d in date_list:
            queue.put_nowait(d)
            
        sem = asyncio.Semaphore(SEMAPHORE_LIMIT)
        
        # Create workers (e.g. 5 concurrent workers consuming the queue)
        # Actually let's create 5 distinct tasks that loop until queue empty
        tasks = []
        for _ in range(SEMAPHORE_LIMIT):
            tasks.append(asyncio.create_task(worker(sem, context, args.keyword, queue, seen_urls)))
            
        await asyncio.gather(*tasks)
        
        await browser.close()
        
    logger.info("Collection Complete.")

if __name__ == "__main__":
    asyncio.run(main())
