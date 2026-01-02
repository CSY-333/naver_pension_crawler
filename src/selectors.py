from typing import List, Dict, Optional

class SearchPageSelectors:
    """Selectors for the search.naver.com news results."""
    # The container for the news list (New UI)
    NEWS_LIST_WRAPPER = ".fds-news-item-list-tab"
    
    # Individual news item card
    NEWS_ITEM = ".fds-news-item-list-tab > div"
    
    # The "Naver News" direct link 
    # Use href check for robustness as classes are dynamic
    NAVER_NEWS_LINK = "a[href*='n.news.naver.com']"
    
    # Next page button for search results
    # Naver News Search UI often uses 'a.btn_next' but strict selector might fail?
    # Trying list for redundancy.
    NEXT_PAGE = [
        "a.btn_next", 
        ".sc_page_inner .btn_next",
        "div.sc_page > a.btn_next",
        "a[role='button'].btn_next"
    ]

class ArticlePageSelectors:
    """Selectors for the article detail page."""
    # Title is usually in the header
    TITLE = [
        "h2#title_area",
        "h2.media_end_head_headline",
        "div.article_info h3",       # Old layout
        ".end_tit"                   # Very old layout
    ]
    
    # Canonical link often found in head > link[rel='canonical']
    # But for extraction from body if needed:
    LINK_ELEMENT = "head > link[rel='canonical']"
    
    # Comment count is dynamic, often in a specific count element
    # Note: These are often rendered by JS
    COMMENT_COUNT = [
        ".u_cbox_count",                             # Most common (Generic)
        "span.u_cbox_count",                         # Specific
        "a.media_end_head_info_datestamp_bunch span.u_cbox_count",
        "div.u_cbox_area span.u_cbox_count"
    ]
    
    # Content area (if we needed body text, but we don't for this task)
    BODY = ["#dic_area", "#articleBodyContents"]

class CommentSelectors:
    """Selectors for the comment section (iframe or JS loaded)."""
    # The container that holds the comment list
    LIST_Container = ".u_cbox_content_wrap"
    
    # Individual comment items
    COMMENT_ITEM = "li.u_cbox_comment"
    
    # Within a comment item
    NICKNAME = "span.u_cbox_nick"
    CONTENT = "span.u_cbox_contents"
    DATE = "span.u_cbox_date"
    
    # Pagination / "More" buttons
    MORE_BUTTON = "a.u_cbox_btn_more"
    NEXT_PAGE_BUTTON = "a.u_cbox_next"
    
    # For handling sticker comments (they might lack text content)
    STICKER = "span.u_cbox_sticker_url"
    IMAGE = "span.u_cbox_image_url"

class DemographicSelectors:
    """Selectors for the demographic visualization charts."""
    # Container for the chart area
    CHART_AREA = "div.u_cbox_chart_cont"
    
    # Gender ratio text/bar
    MALE_RATIO = [
        ".u_cbox_chart_male .u_cbox_chart_per",
    ]
    FEMALE_RATIO = [
        ".u_cbox_chart_female .u_cbox_chart_per",
    ]
    
    # Age distribution
    # Usually a list of percentages corresponding to 10s, 20s, 30s, 40s, 50s, 60+, 70+
    # We use nth-child to be precise as the structure is a list
    AGE_ITEMS = [
        ".u_cbox_chart_age .u_cbox_chart_progress:nth-child(1) .u_cbox_chart_per", # 10s
        ".u_cbox_chart_age .u_cbox_chart_progress:nth-child(2) .u_cbox_chart_per", # 20s
        ".u_cbox_chart_age .u_cbox_chart_progress:nth-child(3) .u_cbox_chart_per", # 30s
        ".u_cbox_chart_age .u_cbox_chart_progress:nth-child(4) .u_cbox_chart_per", # 40s
        ".u_cbox_chart_age .u_cbox_chart_progress:nth-child(5) .u_cbox_chart_per", # 50s
        ".u_cbox_chart_age .u_cbox_chart_progress:nth-child(6) .u_cbox_chart_per", # 60s
        ".u_cbox_chart_age .u_cbox_chart_progress:nth-child(7) .u_cbox_chart_per"  # 70s+
    ]

def get_selector(page, selectors: List[str]) -> Optional[str]:
    """Helper to find which selector is active on the page."""
    for sel in selectors:
        if page.locator(sel).first.is_visible():
            return sel
    return None
