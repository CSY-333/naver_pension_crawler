import asyncio
import logging
import random
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Set, Optional

import aiohttp
from aiohttp import ClientTimeout
from playwright.async_api import async_playwright, BrowserContext

from . import config as config_module
from .parsers import (
    parse_search_results,
    parse_article_details,
    fetch_comments_api,
    parse_demographics,
    fetch_search_results_http,
)
from .storage import CSVExporter
from .monitor import StatusMonitor

logger = logging.getLogger(__name__)


class NaverNewsCrawler:
    """
    Hybrid 파이프라인
    - 검색: HTTP 우선 → 재시도 → 페이지 단위 Playwright 폴백
    - 댓글: API 우선(비동기, 페이지 세마포어) + socialInfo 없을 때만 UI 폴백
    - 저장: 배치 + tmp→replace, 고유 배치 파일명
    """

    def __init__(self, run_id: Optional[str] = None):
        self.results_articles: List[Dict[str, Any]] = []
        self.results_comments: List[Dict[str, Any]] = []
        self.seen_urls: Set[str] = set()
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.exporter = CSVExporter(self.run_id)
        self.article_buffer: List[Dict[str, Any]] = []
        self.comment_buffer: List[Dict[str, Any]] = []
        self.article_buffer_size = config_module.config.storage.batch_size
        self.comment_buffer_size = config_module.config.storage.batch_size
        self.http_session: Optional[aiohttp.ClientSession] = None

        self.article_sem = asyncio.Semaphore(config_module.config.crawler.article_sem)
        self.page_sem = asyncio.Semaphore(config_module.config.crawler.page_sem)
        self.forbidden_streak = 0
        self.stop_due_to_403 = False

        self.stats = {
            "scanned": 0,
            "matched": 0,
            "collected": 0,
            "comments_total": 0,
            "errors": [],
            "fallback_search": 0,
            "fallback_demographics": 0,
            "forbidden": 0,
        }
        self.monitor = StatusMonitor(self.exporter.run_dir)
        self.monitor.set_stage("READY")
        self.stopped = False
        
        # Load history to prevent duplicates
        self.load_existing_history()

    def load_existing_history(self):
        """Loads previously collected URLs from the output directory to avoid duplicates."""
        base_dir = config_module.config.storage.output_dir
        if not os.path.exists(base_dir):
            return

        count = 0
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                if "articles" in file and file.endswith(".jsonl"):
                    path = os.path.join(root, file)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            for line in f:
                                try:
                                    item = json.loads(line)
                                    url = item.get("url")
                                    if url:
                                        self.seen_urls.add(url)
                                        count += 1
                                except:
                                    pass
                    except Exception as e:
                        logger.warning(f"Failed to read history file {path}: {e}")
        
        if count > 0:
            logger.info(f"Loaded {count} existing URLs from {base_dir} to avoid duplicates.")


    async def run(self):
        if self.stopped:
            return

        logger.info(f"Starting crawler run {self.run_id}...")
        logger.info(f"Config: demographics_ui_fallback={config_module.config.filters.demographics_ui_fallback}")
        
        # 1. Init browsert_stage("STARTING")
        self.monitor.set_stage("STARTING")

        # Shared HTTP session for search + comments
        timeout = ClientTimeout(total=config_module.config.crawler.http_total_timeout)
        headers = {"User-Agent": config_module.config.crawler.user_agent}
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as http_session:
            self.http_session = http_session
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=config_module.config.crawler.headless)
                context = await browser.new_context(user_agent=config_module.config.crawler.user_agent)
                self.monitor.set_stage("SEARCHING")

                for keyword in config_module.config.search.keywords:
                    if self.stop_due_to_403:
                        break
                    try:
                        self.monitor.set_keyword(keyword)
                        await self.process_keyword_search(context, http_session, keyword)
                    except Exception as e:
                        logger.error(f"Error processing keyword '{keyword}': {e}")
                        self.stats["errors"].append({"step": f"keyword_{keyword}", "error": str(e)})
                        self.monitor.update_stats(self.stats)

                await browser.close()

        # Flush remaining buffers
        self.flush_buffers(force=True)
        self.monitor.set_stage("COMPLETED")
        self.monitor.update_stats(self.stats)
        logger.info(f"Crawl finished. Stats: {self.stats}")
        return self.results_articles, self.results_comments

    async def process_keyword_search(self, context: BrowserContext, http_session: aiohttp.ClientSession, keyword: str):
        logger.info(f"Searching for keyword: {keyword}")
        page = await context.new_page()
        base_url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sort={config_module.config.search.sort_method}"
        if config_module.config.search.start_date and config_module.config.search.end_date:
            base_url += f"&pd=3&ds={config_module.config.search.start_date}&de={config_module.config.search.end_date}"

        prev_count: Optional[int] = None
        low_streak = 0
        current_page = 0
        total_pages = config_module.config.search.max_pages

        try:
            while current_page < total_pages:
                if self.stop_due_to_403 or self.stats["collected"] >= config_module.config.filters.max_articles:
                    break

                current_page += 1
                start_idx = (current_page - 1) * 10 + 1
                page_url = f"{base_url}&start={start_idx}"

                # HTTP fetch
                articles = await fetch_search_results_http(http_session, keyword, current_page - 1)
                fallback_needed = False

                # [FIX]: Check for invalid data (e.g. Unknown Date) that implies JS-only content
                if any(a.get("date") == "Unknown Date" or a.get("title") == "네이버뉴스" for a in articles):
                    logger.warning(f"HTTP fetch returned invalid data (Unknown Date) for page {current_page}. Triggering Playwright fallback.")
                    articles = [] # Force fallback

                if len(articles) == 0:
                    fallback_needed = True  # selector 0건 → 즉시 폴백
                else:
                    # 상대적 급락 감지
                    if prev_count and len(articles) < prev_count * config_module.config.search.low_drop_ratio:
                        # HTTP 한 번 더 재시도
                        for _ in range(config_module.config.search.http_retry_on_low):
                            retry_articles = await fetch_search_results_http(http_session, keyword, current_page - 1)
                            if len(retry_articles) > len(articles):
                                articles = retry_articles
                                break
                        if len(articles) < prev_count * config_module.config.search.low_drop_ratio:
                            low_streak += 1
                        else:
                            low_streak = 0
                    else:
                        low_streak = 0

                    if low_streak >= config_module.config.search.low_streak_trigger:
                        fallback_needed = True
                        low_streak = 0

                if fallback_needed:
                    self.stats["fallback_search"] += 1
                    await page.goto(page_url, wait_until="domcontentloaded", timeout=config_module.config.crawler.page_load_timeout)
                    await asyncio.sleep(random.uniform(0.8, 1.2))
                    articles = await parse_search_results(page)

                prev_count = len(articles) if articles else prev_count
                if not articles:
                    logger.info("No articles found on this page.")
                    continue

                logger.info(f"Page {current_page}: {len(articles)} articles")

                tasks = []
                for article in articles:
                    if self.stats["collected"] >= config_module.config.filters.max_articles or self.stop_due_to_403:
                        break
                    if article["url"] in self.seen_urls:
                        continue
                    self.seen_urls.add(article["url"])
                    self.stats["scanned"] += 1
                    tasks.append(asyncio.create_task(self._process_article_guard(context, article, keyword)))

                if tasks:
                    await asyncio.gather(*tasks)
                    self.monitor.update_stats(self.stats)

        finally:
            await page.close()

    async def _process_article_guard(self, context: BrowserContext, article_meta: Dict[str, Any], keyword: str):
        async with self.article_sem:
            await self.process_article(context, article_meta, keyword)

    async def process_article(self, context: BrowserContext, article_meta: Dict[str, Any], keyword: str):
        url = article_meta["url"]
        oid = article_meta.get("oid")
        aid = article_meta.get("aid")
        aid = article_meta.get("aid")
        title = article_meta.get("title")
        date_str = article_meta.get("date", "Unknown")

        data = {
            "run_id": self.run_id,
            "collected_at_kst": datetime.now().isoformat(),
            "published_at": date_str,
            "keyword": keyword,
            "title": title,
            "url": url,
            "oid": oid,
            "aid": aid,
            "section": None,
            "demographic_available": False,
            "comments_collected": False,
            "comments_collected_n": 0,
        }

        # 1) 댓글 API + socialInfo (우선)
        comments: List[Dict[str, Any]] = []
        social_meta: Dict[str, Any] = {}
        try:
            comments, social_meta = await fetch_comments_api(
                oid,
                aid,
                max_comments=config_module.config.filters.max_comments,
                session=self.http_session,
                page_sem=self.page_sem,
                stop_on_403=config_module.config.crawler.stop_on_403_run,
                max_retry_429=config_module.config.crawler.max_retry_429,
                max_retry_5xx=config_module.config.crawler.max_retry_5xx,
                backoff_base=config_module.config.crawler.backoff_base,
                timeout=config_module.config.crawler.http_total_timeout,
            )
        except PermissionError:
            self.stats["forbidden"] += 1
            self.forbidden_streak += 1
            if config_module.config.crawler.stop_on_403_run and self.forbidden_streak >= 2:
                self.stop_due_to_403 = True
            return
        except Exception as e:
            logger.error(f"Error fetching comments for {url}: {e}")
            self.stats["errors"].append({"url": url, "type": "api_error", "error": str(e)})
            return

        self.forbidden_streak = 0
        
        # [NEW] Skip logic for URL-only collection removed from here
        # Moved to after filter check

        comment_count_api = social_meta.get("total_count", len(comments))

        # demographic from socialInfo if available
        social = social_meta.get("socialInfo") or {}
        if social:
            try:
                male = float(social.get("male", 0))
                female = float(social.get("female", 0))
                ages = social.get("age", {})
                data.update(
                    {
                        "male_ratio": male,
                        "female_ratio": female,
                        "age_10s": float(ages.get("10", 0)),
                        "age_20s": float(ages.get("20", 0)),
                        "age_30s": float(ages.get("30", 0)),
                        "age_40s": float(ages.get("40", 0)),
                        "age_50s": float(ages.get("50", 0)),
                        "age_60_plus": float(ages.get("60", 0)) + float(ages.get("70", 0)),
                        "demographic_available": True,
                    }
                )
            except Exception as e:
                logger.warning(f"socialInfo parse error for {url}: {e}")

        # 2) socialInfo 없거나 비어있으면 UI 폴백 (API count가 낮을 때도 확인)
        # API count가 threshold보다 낮으면 UI에서 다시 확인
        need_ui_fallback = False
        if not data.get("demographic_available"):
            need_ui_fallback = True
        elif comment_count_api < config_module.config.filters.comment_threshold and config_module.config.filters.demographics_ui_fallback:
             # API count is low, double check with UI if enabled
             need_ui_fallback = True

        # Debug log
        # logger.info(f"Processing {url}: need_fallback={need_ui_fallback}, config_fallback={config_module.config.filters.demographics_ui_fallback}")

        # Initialize comment_count_ui for safe access later
        comment_count_ui = comment_count_api

        if need_ui_fallback and config_module.config.filters.demographics_ui_fallback:
            self.stats["fallback_demographics"] += 1
            article_page = await context.new_page()
            try:
                await article_page.goto(url, wait_until="domcontentloaded", timeout=config_module.config.crawler.page_load_timeout)
                await asyncio.sleep(random.uniform(0.5, 1.0))
                demog = await parse_demographics(article_page)
                # Only update if valid
                if demog.get("demographic_available"):
                    data.update(demog)
                
                details = await parse_article_details(article_page, url)
                comment_count_ui = details.get("comment_count_ui", 0)
                
                # Trust UI count if API failed to capture it
                if comment_count_ui > comment_count_api:
                    comment_count_api = comment_count_ui
                    
            except Exception as e:
                logger.error(f"Demographics fallback failed {url}: {e}")
                self.stats["errors"].append({"url": url, "type": "demographic_error", "error": str(e)})
            finally:
                await article_page.close()

        data.update(
            {
                "comment_count_ui": comment_count_ui,
                "comment_count": comment_count_api,
            }
        )

        # 4. Filter check
        # Update demographics if valid
        if demog.get("demographic_available"):
             data.update(demog)

        if not self._check_filters(data, demog):
            logger.info(f"Filtered out: {url} (Comments: {comment_count_ui}, Demog: {data.get('demographic_available')})")
            return

        # 5. [NEW] Stop if only_urls is True
        if getattr(config_module.config.crawler, "only_urls", False):
            logger.info(f"[Meta-Only] Collected article metadata: {title}")
            self.results_articles.append(data)
            self.stats["collected"] += 1
            self.stats["matched"] += 1
            
            # Save and Return
            self.article_buffer.append(data)
            self.flush_buffers()
            return
            
        # Strict user requirement: "Ensure all have statistics"
        if not data.get("demographic_available"):
            logger.info(f"Skip {url} [{date_str}] (No demographics available)")
            return

        # 3) 저장 및 통계
        data["comments_collected"] = True
        data["comments_collected_n"] = len(comments)
        data["comment_count"] = comment_count_api
        self.stats["comments_total"] += len(comments)
        self.stats["collected"] += 1
        logger.info(f"Collected {url} [{date_str}] (Comments: {comment_count_api})")
        self.results_articles.append(data)
        self.results_comments.extend(comments)

        # Buffering + batch write
        self.article_buffer.append(data)
        if comments:
            for c in comments:
                c["run_id"] = self.run_id
                c["article_url"] = url
            self.comment_buffer.extend(comments)

        self.flush_buffers()

    def flush_buffers(self, force: bool = False):
        if force or len(self.article_buffer) >= self.article_buffer_size:
            self.exporter.save_articles_batch(self.article_buffer)
            self.article_buffer.clear()
        if force or len(self.comment_buffer) >= self.comment_buffer_size:
            self.exporter.save_comments_batch(self.comment_buffer)
            self.comment_buffer.clear()

    def _check_filters(self, data: Dict[str, Any], demog: Dict[str, Any]) -> bool:
        """
        Check if article meets filter criteria (Keywords, Comment Count).
        """
        # 1. Comment Threshold
        threshold = config_module.config.filters.comment_threshold
        count = data.get("comment_count", 0)
        
        # Note: 'comment_count' in data might be API count or UI count depending on fallback logic earlier.
        # Strict check:
        if count < threshold:
            return False
            
        # 2. Title Keywords (Optional - ensure relevant)
        # filter_keywords = config_module.config.filters.keywords
        # if filter_keywords and data.get("title"):
        #     if not any(k in data["title"] for k in filter_keywords):
        #         return False

        return True

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='config/config.yaml')
    args = parser.parse_args()
    
    # Load config manually if needed or rely on config module loading it securely
    # But since config imports from env or direct, we might need to set it.
    # Actually config.py likely handles loading.
    # Just need to run.
    
    # Force RELOAD config from args if supported?
    # For now, assume config module loads from file if we set env or similar.
    # Wait, config.py reads file?
    
    if args.config:
        # Reload config from the specified file
        config_module.config = config_module.Config.load(args.config)

    crawler = NaverNewsCrawler()
    asyncio.run(crawler.run())

