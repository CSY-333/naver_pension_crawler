import yaml
import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SearchConfig:
    keywords: List[str] = field(default_factory=lambda: ["국민연금"])
    max_pages: int = 2  # Number of search result pages to scan per keyword
    sort_method: int = 0  # 0: relevance, 1: date(latest)
    start_date: str = "" # Format: YYYY.MM.DD
    end_date: str = ""   # Format: YYYY.MM.DD
    # Fallback heuristics / HTTP tuning
    low_drop_ratio: float = 0.5          # if current count < prev * ratio -> low
    low_streak_trigger: int = 2          # consecutive low pages before browser fallback
    http_retry_on_low: int = 1           # retry HTTP once when low before fallback
    force_http: bool = True              # prefer HTTP parsing over Playwright for search
    request_timeout: float = 8.0         # seconds for search HTTP


@dataclass
class CrawlerConfig:
    headless: bool = True
    request_delay_min: float = 0.5
    request_delay_max: float = 2.0
    retry_attempts: int = 3
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    page_load_timeout: int = 30000  # ms
    # Concurrency / rate
    article_sem: int = 5           # concurrent articles
    page_sem: int = 10             # concurrent comment pages overall
    backoff_base: float = 2.0      # seconds for 429/5xx backoff
    max_retry_429: int = 3
    max_retry_5xx: int = 3
    stop_on_403_run: bool = True   # run-level stop when repeated 403
    http_total_timeout: float = 30.0  # seconds per HTTP request
    only_urls: bool = False  # If true, skips comment body collection


@dataclass
class FilterConfig:
    # Default keywords target 국민연금 related news; empty list => match all
    keywords: List[str] = field(default_factory=lambda: ["국민연금", "연금", "연금 개혁", "연금개혁", "기초연금", "퇴직연금", "공적연금"])
    comment_threshold: int = 10
    max_comments: int = 300
    max_articles: int = 500 # Target number of collected articles
    store_min_rows: bool = True
    demographics_ui_fallback: bool = True  # when socialInfo missing


@dataclass
class StorageConfig:
    # Default to a "GPR" folder in the user's home directory (e.g., C:/Users/Name/Documents/GPR or similar)
    # Or simply "./GPR" relative to execution. Let's use relative for portability unless absolute is needed.
    # User requested: "Relative paths or user-home based".
    # Using relative path is safest for a self-contained project.
    output_dir: str = "GPR" 
    articles_filename: str = "articles_pension.jsonl"
    comments_filename: str = "comments_pension.jsonl"
    encoding: str = "utf-8"  # JSONL typically uses standard utf-8
    batch_size: int = 20
    tmp_suffix: str = ".tmp"
    unique_batch_files: bool = True  # avoid collision on rerun


@dataclass
class Config:
    search: SearchConfig = field(default_factory=SearchConfig)
    crawler: CrawlerConfig = field(default_factory=CrawlerConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)

    @classmethod
    def load(cls, config_path: str = "config/config.yaml") -> 'Config':
        """Load configuration from a YAML file."""
        if not os.path.exists(config_path):
            return cls()

        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        return cls(
            search=SearchConfig(**data.get('search', {})),
            crawler=CrawlerConfig(**data.get('crawler', {})),
            filters=FilterConfig(**data.get('filters', {})),
            storage=StorageConfig(**data.get('storage', {}))
        )


# Global instance for easy access if needed
config = Config.load()
