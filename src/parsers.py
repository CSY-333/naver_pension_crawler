import re
import json
import asyncio
import aiohttp
import requests
import logging
from typing import List, Dict, Optional, Any, Tuple
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from playwright.async_api import Page
from .selectors import SearchPageSelectors, ArticlePageSelectors, DemographicSelectors
from .config import config

logger = logging.getLogger(__name__)

async def parse_search_results(page: Page) -> List[Dict[str, str]]:
    """
    Extracts 'Naver News' URLs and titles from the search results page.
    Returns a list of dicts: {'url': str, 'title': str, 'oid': str, 'aid': str}
    """
    articles = []
    seen = set()
    
    # Wait for list to load
    try:
        await page.locator(SearchPageSelectors.NEWS_LIST_WRAPPER).wait_for(state="visible", timeout=5000)
    except:
        logger.warning("Search result list not found/visible.")
        return []

    # Iterate over news items
    items = await page.locator(SearchPageSelectors.NEWS_ITEM).all()
    for item in items:
        try:
            # Check for "Naver News" link
            naver_link = item.locator(SearchPageSelectors.NAVER_NEWS_LINK).first
            if await naver_link.is_visible():
                href = await naver_link.get_attribute("href")
                
                # Title - Try standard class, then fallback to finding the main article link
                title_el = item.locator("a.news_tit").first
                if not await title_el.is_visible():
                    # Fallback: Find the link that is NOT the "Naver News" button but goes to naver news
                    # Or simpler: The "Naver News" button usually points to the same article? 
                    # No, "Naver News" button points to n.news.naver.com, title might point to original press.
                    # Wait, we WANT n.news.naver.com article.
                    # The "Naver News" button href IS the one we want to crawl.
                    # So we can use that href.
                    # Use the text of any large link in the item as title?
                    # Let's try to get text from the 'Naver News' link itself? No, that says "네이버뉴스".
                    # Let's try ".news_contents .news_tit" or similar.
                    # New UI class seen in valid results: .yuu64AGiOBzaFbBUUZbL (dynamic)
                    # Let's try generic: `a` tag with text length > 10?
                    pass

                title = await title_el.text_content() if await title_el.is_visible() else "No Title"
                if title == "No Title":
                     # Try to find the title link by exclusion
                     links = await item.locator("a").all()
                     for link in links:
                         txt = await link.text_content()
                         url = await link.get_attribute("href")
                         # Title usually has long text
                         if txt and len(txt) > 10 and "네이버뉴스" not in txt:
                             title = txt
                             break
                
                date_text = "Unknown Date"
                try:
                    # Try to find the date info (usually inside .info_group or .info)
                    info_els = await item.locator(".info_group .info").all()
                    found_date = False
                    for el in info_els:
                        txt = await el.text_content()
                        if txt and ("전" in txt or "." in txt) and "네이버뉴스" not in txt:
                            date_text = txt.strip()
                            found_date = True
                            break
                    
                    # [Fallback] New UI: Scan generic spans for date patterns
                    if not found_date:
                        date_pattern = re.compile(r"(\d{4}\.\d{2}\.\d{2}|\d+(분|시간|일|주) 전)")
                        # Limit to first 30 elements to avoid performance hit
                        spans = await item.locator("span").all()
                        for sp in spans[:30]:
                            txt = await sp.text_content()
                            if txt and len(txt) < 20 and date_pattern.search(txt):
                                date_text = txt.strip()
                                break
                except:
                    pass

                if href:
                    oid, aid = extract_oid_aid(href)
                    if oid and aid:
                        clean_link = f"https://n.news.naver.com/mnews/article/{oid}/{aid}"
                        if clean_link not in seen:
                            seen.add(clean_link)
                            articles.append({
                                "url": clean_link,
                                "title": title.strip(),
                                "date": date_text,
                                "oid": oid,
                                "aid": aid
                            })
        except Exception as e:
            continue
            
    return articles

def extract_oid_aid(url: str) -> (Optional[str], Optional[str]):
    """
    Extracts oid and aid from a naver news URL.
    """
    # Pattern 1: .../article/001/0001234567
    match = re.search(r"article/(\d+)/(\d+)", url)
    if match:
        return match.group(1), match.group(2)
    
    # Pattern 2: query params (less common in modern canonicals but possible)
    match_oid = re.search(r"oid=(\d+)", url)
    match_aid = re.search(r"aid=(\d+)", url)
    if match_oid and match_aid:
        return match_oid.group(1), match_aid.group(1)
        
    return None, None

async def parse_article_details(page: Page, url: str) -> Dict[str, Any]:
    """
    Extracts title and comment count from the article page UI (as backup/verification).
    """
    title = ""
    for sel in ArticlePageSelectors.TITLE:
        if await page.locator(sel).first.is_visible():
            title = await page.locator(sel).first.text_content()
            break
            
    # Comment count (UI) - useful to cross-check with API or if API fails
    comment_count = 0
    comment_count = 0
    try:
        # Prioritize bottom comment area if present (lazy loaded)
        # Attempt to scroll to comment area first if not already done
        try:
             await page.locator(".u_cbox_wrap").first.scroll_into_view_if_needed(timeout=1000)
        except:
             pass

        for sel in ArticlePageSelectors.COMMENT_COUNT:
            try:
                # Wait briefly for element to appear
                el = page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    text = await el.text_content()
                    text = text.replace(",", "")
                    if text.isdigit():
                        comment_count = int(text)
                        break
            except:
                continue
    except:
        pass

    return {
        "title": title.strip(),
        "url": url,
        "comment_count_ui": comment_count
    }

def parse_jsonp_payload(text: str) -> Dict[str, Any]:
    """Robust JSONP stripper without regex; tolerant to callback name changes/whitespace."""
    start = text.find("(")
    end = text.rfind(")")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Invalid JSONP wrapper")
    payload = text[start + 1 : end]
    return json.loads(payload)


async def fetch_comments_api(
    oid: str,
    aid: str,
    *,
    max_comments: int = 300,
    session: Optional[aiohttp.ClientSession] = None,
    page_sem: Optional[asyncio.Semaphore] = None,
    stop_on_403: bool = True,
    max_retry_429: int = 3,
    max_retry_5xx: int = 3,
    backoff_base: float = 1.0,
    timeout: float = 8.0,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fetch comments + socialInfo using Naver Comment API.
    Returns (comments, meta) where meta includes socialInfo and counts.
    """
    object_id = f"news{oid},{aid}"
    base_url = "https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json"
    local_session = session is None
    headers = {
        "User-Agent": config.crawler.user_agent,
        "Referer": f"https://n.news.naver.com/mnews/article/comment/{oid}/{aid}"
    }
    timeout_obj = aiohttp.ClientTimeout(total=timeout)
    if local_session:
        session = aiohttp.ClientSession(headers=headers, timeout=timeout_obj)
    comments: List[Dict[str, Any]] = []
    meta: Dict[str, Any] = {"socialInfo": None, "total_count": 0}

    async def _request_page(page_num: int, initialize: bool) -> Dict[str, Any]:
        # Templates to try in order. If one returns >0 comments, we trust it.
        # If all return 0, we assume 0.
        templates = ["view_politics", "default_society", "default_economy", "default_view", "view_it"]
        
        best_payload = {}
        max_count = -1
        
        for tmpl in templates:
            params = {
                "ticket": "news",
                "templateId": tmpl,
                "pool": "cbox5",
                "lang": "ko",
                "country": "KR",
                "objectId": object_id,
                "pageSize": 100,
                "indexSize": 10,
                "page": page_num,
                "initialize": "true" if initialize else "false",
                "useAltSort": "true",
                "replyPageSize": 20
            }
            
            try:
                # Use requests (sync) in a thread to mimic notebook behavior exactly
                # This bypasses potential aiohttp TLS fingerprinting fail
                def fetch_sync():
                    return requests.get(base_url, params=params, headers=headers, timeout=timeout)
                
                if page_sem:
                    async with page_sem:
                        resp = await asyncio.to_thread(fetch_sync)
                else:
                    resp = await asyncio.to_thread(fetch_sync)

                status = resp.status_code
                text = resp.text
                
                if status == 200:
                    payload = parse_jsonp_payload(text)
                    
                    # Check count from this template
                    cnt = payload.get("result", {}).get("count", {}).get("comment", 0)
                    
                    # If we found comments, this is likely the correct template
                    if cnt > max_count:
                        max_count = cnt
                        best_payload = payload
                    
                    # If we found significant comments, stop searching templates
                    if cnt > 0:
                        return best_payload
                        
                    # If 0, try next template
                    break
                    
                if status == 403:
                    logger.warning(f"403 for {oid}/{aid} page {page_num} tmpl {tmpl}")
                    if stop_on_403:
                        raise PermissionError("403 Forbidden")
                    return {}
                    
                logger.warning(f"API Error {status} for {oid}/{aid} page {page_num} tmpl {tmpl}")
                break # Try next template
                
            except Exception as e:
                logger.warning(f"Template {tmpl} error: {e}")
                continue
                
        return best_payload

    try:
        # First page to learn totalPages + socialInfo
        first_payload = await _request_page(1, True)
        result = first_payload.get("result", {}) if first_payload else {}
        meta["socialInfo"] = result.get("socialInfo")
        meta["total_count"] = result.get("count", {}).get("comment", 0)

        comment_list = result.get("commentList", [])
        for c in comment_list:
            if len(comments) >= max_comments:
                break
            comments.append({
                "comment_id": str(c.get("commentNo")),
                "comment_text": c.get("contents", ""),
                "comment_created_at": c.get("regTime", ""),
                "author": c.get("maskedUserName", "") or c.get("userName", ""),
                "sympathy_count": c.get("sympathyCount", 0),
                "antipathy_count": c.get("antipathyCount", 0)
            })

        page_model = result.get("pageModel", {})
        total_pages = page_model.get("totalPages", 0)

        if total_pages > 1 and len(comments) < max_comments:
            tasks = []
            for page_num in range(2, total_pages + 1):
                if len(comments) >= max_comments:
                    break
                tasks.append(_request_page(page_num, False))

            if tasks:
                payloads = await asyncio.gather(*tasks, return_exceptions=True)
                for payload in payloads:
                    if isinstance(payload, Exception):
                        # Already logged
                        continue
                    result = payload.get("result", {})
                    for c in result.get("commentList", []):
                        if len(comments) >= max_comments:
                            break
                        comments.append({
                            "comment_id": str(c.get("commentNo")),
                            "comment_text": c.get("contents", ""),
                            "comment_created_at": c.get("regTime", ""),
                            "author": c.get("maskedUserName", "") or c.get("userName", ""),
                            "sympathy_count": c.get("sympathyCount", 0),
                            "antipathy_count": c.get("antipathyCount", 0)
                        })
    finally:
        if local_session and session:
            await session.close()

    return comments, meta


async def fetch_search_results_http(session: aiohttp.ClientSession, keyword: str, page_idx: int) -> List[Dict[str, str]]:
    """
    Fast HTML fetch for search results (no browser).
    Returns list of article dicts.
    """
    start = page_idx * 10 + 1
    params = {
        "where": "news",
        "query": keyword,
        "sort": config.search.sort_method,
        "start": start,
    }
    url = f"https://search.naver.com/search.naver?{urlencode(params)}"
    resp = await session.get(url)
    if resp.status != 200:
        logger.warning(f"Search HTTP status {resp.status} page {page_idx+1}")
        return []
    html = await resp.text()
    soup = BeautifulSoup(html, "html.parser")
    articles = []
    seen = set()
    # Look for direct Naver News links
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "n.news.naver.com" not in href:
            continue
        oid, aid = extract_oid_aid(href)
        if not (oid and aid):
            continue
        clean_link = f"https://n.news.naver.com/mnews/article/{oid}/{aid}"
        if clean_link in seen:
            continue
        title = a.get_text(strip=True) or "No Title"
        # Try nearby title anchor
        parent = a.find_parent()
        if parent:
            title_candidate = parent.find("a", class_="news_tit")
            if title_candidate and title_candidate.get_text(strip=True):
                title = title_candidate.get_text(strip=True)
        # Try to find date in .info_group .info
        date_text = "Unknown Date"
        try:
            parent = a.find_parent("div", class_="news_area")
            if parent:
                infos = parent.select(".info_group .info")
                for info in infos:
                    txt = info.get_text(strip=True)
                    if ("전" in txt or "." in txt) and "네이버뉴스" not in txt:
                        date_text = txt
                        break
        except:
             pass

        seen.add(clean_link)
        articles.append({
            "url": clean_link,
            "title": title,
            "date": date_text,
            "oid": oid,
            "aid": aid
        })

    return articles

async def parse_demographics(page: Page) -> Dict[str, Any]:
    """
    Extracts gender and age distribution.
    """
    data = {
        "male_ratio": float("nan"),
        "female_ratio": float("nan"),
        "age_10s": float("nan"),
        "age_20s": float("nan"),
        "age_30s": float("nan"),
        "age_40s": float("nan"),
        "age_50s": float("nan"),
        "age_60_plus": float("nan"),
        "demographic_available": False
    }
    
    # Check if chart area exists
    try:
        # First ensure comment section is loaded - scroll to bottom
        # Sometimes chart only loads when scrolled into view
        try:
             # Try to find comment area to scroll to specifically
             comment_area = page.locator("#comment_area, .u_cbox_wrap").first
             if await comment_area.is_visible():
                  await comment_area.scroll_into_view_if_needed()
                  await asyncio.sleep(1.0) # wait for lazy load
             else:
                  # Fallback scroll to bottom
                  await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                  await asyncio.sleep(1.0)
        except:
             pass

        chart_locator = page.locator(DemographicSelectors.CHART_AREA).first
        # Don't wait too long, some articles don't have it
        if await chart_locator.is_visible(timeout=3000):
            await chart_locator.scroll_into_view_if_needed()
        else:
            return data
    except:
        return data

    try:
        # Gender
        for sel in DemographicSelectors.MALE_RATIO:
            if await page.locator(sel).first.is_visible():
                txt = await page.locator(sel).first.text_content()
                data["male_ratio"] = float(txt.replace("%", "").strip())
                break
                
        for sel in DemographicSelectors.FEMALE_RATIO:
            if await page.locator(sel).first.is_visible():
                txt = await page.locator(sel).first.text_content()
                data["female_ratio"] = float(txt.replace("%", "").strip())
                break
        
        # Age
        age_keys = ["age_10s", "age_20s", "age_30s", "age_40s", "age_50s", "age_60_plus"]
        # New selectors are specific per age group, so we iterate them
        # Note: Selector list has 7 items now (including 70s).
        # We will map them to our stored keys. 60+ will aggregate 60s and 70s if we want, or just take 60s?
        # Original requirement: 6 buckets. So maybe sum 60s and 70s? or just store what we have.
        # Let's read them all first.
        
        age_values = []
        for sel in DemographicSelectors.AGE_ITEMS:
            if await page.locator(sel).first.is_visible():
                 txt = await page.locator(sel).first.text_content()
                 age_values.append(float(txt.replace("%", "").strip()))
            else:
                 age_values.append(0.0)
                 
        if len(age_values) >= 6:
            data["age_10s"] = age_values[0]
            data["age_20s"] = age_values[1]
            data["age_30s"] = age_values[2]
            data["age_40s"] = age_values[3]
            data["age_50s"] = age_values[4]
            
            # Combine 60s and 70s for "60_plus" if 70s exists
            if len(age_values) >= 7:
                 data["age_60_plus"] = age_values[5] + age_values[6]
            else:
                 data["age_60_plus"] = age_values[5]

            data["demographic_available"] = True
                
    except Exception as e:
        logger.warning(f"Error parsing demographics: {e}")
        pass
        
    return data
