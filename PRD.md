Product Requirements Document: Naver News Comment Collection Pipeline (Hybrid Search+API)

1. Overview
   1.1 Purpose
   Build a production-ready web scraping pipeline to collect Naver News articles about specific keywords (e.g., "국민연금") using a Search-based discovery method, and harvest comments efficiently using the Naver Comment API.

   1.2 Background
   Previous section-scanning crawling was inefficient for specific topics. The new "Hybrid" approach uses Naver Search to find relevant articles directly and uses the internal API to collect comments at high speed, while retaining Playwright for demographic data extraction from the UI.

   1.3 Success Criteria

   - Successfully discover articles matching the target keyword (e.g., "국민연금") via search.naver.com
   - Collect comments using the Naver Comment API (high speed, accurate counts)
   - Extract article-level demographic summaries (gender/age) via Playwright
   - Export clean, deduplicated CSV datasets

2. Data Sources
   2.1 Article Discovery

   - Source: https://search.naver.com/search.naver?where=news&query={KEYWORD}
   - Scope: Top N pages of search results (configurable)

     2.2 Comment Collection

   - Source: https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json
   - Method: Direct HTTP requests (simulating browser calls)

     2.3 Demographics

   - Source: Article Detail UI (e.g., https://n.news.naver.com/mnews/article/...)
   - Method: Playwright DOM parsing (Charts/Graphs)

3. Data Schema
   3.1 Article-Level Data (articles_pension.csv)

   - run_id, collected_at_kst
   - keyword (search term used)
   - title, url, oid, aid
   - comment_count (from API)
   - comments_collected_n
   - male_ratio, female_ratio
   - age_10s, age_20s...age_60_plus

     3.2 Comment-Level Data (comments_pension.csv)

   - run_id, article_url
   - comment_id
   - comment_text
   - comment_created_at
   - author (masked)
   - sympathy_count, antipathy_count (available via API)

4. Functional Requirements
   4.1 Article Discovery (Search)

   - FR-1.1: Iterate through Naver News Search results pages for defined keywords.
   - FR-1.2: Extract original Naver News URLs (convert `sports.news.naver.com`, etc. to standard `n.news.naver.com` if possible, or filter for standard news).
   - FR-1.3: Extract `oid` (Office ID) and `aid` (Article ID) from URLs.

     4.2 Comment Collection (API)

   - FR-2.1: Use `requests` or `aiohttp` to call Naver Comment API.
   - FR-2.2: Pagination handling (pageSize=100) until all comments or max_limit reached.
   - FR-2.3: Handle JSONP/JSON responses.

     4.3 Demographic Data Extraction (UI)

   - FR-3.1: Navigate to article page using Playwright.
   - FR-3.2: Parse gender/age charts from the DOM.

     4.4 Data Export

   - FR-4.1: Export to CSV (UTF-8 BOM).

5. Non-Functional Requirements

   - Technology: Python 3.11, Playwright (UI), Requests/Aiohttp (API), Pandas
   - Modularity: Separation of Crawler (Search), API Client (Comments), and Parser (Demographics).
   - Robustness: API rate limiting handling (though Naver is permissive).

6. Configuration Parameters

   - search_keywords: List[str] (e.g., ["국민연금", "기초연금"])
   - max_search_pages: int (depth of search)
   - comment_threshold: int (min comments to collect)
   - max_comments: int (cap per article)

7. Error Handling

   - Invalid OID/AID extraction -> Skip article
   - API Blocking/Error -> Log and retry, or fallback/skip
   - UI structure change -> Log structural error but continue

8. Out of Scope
   - Login/Authentication
   - Sentiment Analysis
