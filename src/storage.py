import json
import os
import logging
from typing import List, Dict, Any
from . import config as config_module

logger = logging.getLogger(__name__)

class CSVExporter:
    """Handles exporting data to CSV files."""
    
    ARTICLE_COLUMNS = [
        "run_id", "collected_at_kst", "section", "title", "url", 
        "comment_count", "comments_collected", "comments_collected_n",
        "male_ratio", "female_ratio", 
        "age_10s", "age_20s", "age_30s", "age_40s", "age_50s", "age_60_plus",
        "demographic_available"
    ]
    
    COMMENT_COLUMNS = [
        "run_id", "article_url", "comment_id", "comment_text", "comment_created_at"
    ]

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.pid = os.getpid()
        
        # Base Output Dir
        self.base_output_dir = config_module.config.storage.output_dir
        if self.base_output_dir.startswith("~"):
            self.base_output_dir = os.path.expanduser(self.base_output_dir)
        else:
            self.base_output_dir = os.path.abspath(self.base_output_dir)

        # Run partition dir
        self.run_dir = os.path.join(self.base_output_dir, f"run_{self.run_id}")
        
        if not os.path.exists(self.run_dir):
            os.makedirs(self.run_dir, exist_ok=True)
            
        self.articles_path = os.path.join(self.run_dir, config_module.config.storage.articles_filename)
        self.comments_path = os.path.join(self.run_dir, config_module.config.storage.comments_filename)
        self.article_batch_idx = 0
        self.comment_batch_idx = 0
            
    def save_article(self, article: Dict[str, Any]):
        """Save a single article to JSONL immediately (Append)."""
        if not article:
            return
            
        # Append to file
        self._append_to_jsonl(article, self.articles_path)

    def save_comments(self, comments: List[Dict[str, Any]]):
        """Save a batch of comments to JSONL immediately (Append)."""
        if not comments:
            return
            
        for comment in comments:
            self._append_to_jsonl(comment, self.comments_path)

    def save_articles_batch(self, articles: List[Dict[str, Any]]):
        """Crash-safe batch write using tmp -> replace. Creates unique batch files when enabled."""
        if not articles:
            return
        self.article_batch_idx += 1
        filename = self._batch_filename(prefix="articles_batch", idx=self.article_batch_idx)
        self._write_batch(articles, filename)

    def save_comments_batch(self, comments: List[Dict[str, Any]]):
        """Crash-safe batch write using tmp -> replace. Creates unique batch files when enabled."""
        if not comments:
            return
        self.comment_batch_idx += 1
        filename = self._batch_filename(prefix="comments_batch", idx=self.comment_batch_idx)
        self._write_batch(comments, filename)
        
    def _append_to_jsonl(self, data: Dict[str, Any], path: str):
        """Helper to append data to JSONL."""
        try:
            with open(path, "a", encoding=config_module.config.storage.encoding) as f:
                json.dump(data, f, ensure_ascii=False)
                f.write("\n")
        except Exception as e:
            logger.error(f"Failed to save data to {path}: {e}")

    def _batch_filename(self, prefix: str, idx: int) -> str:
        if config_module.config.storage.unique_batch_files:
            return os.path.join(self.run_dir, f"{prefix}_{self.run_id}_{idx:04d}_{self.pid}.jsonl")
        return os.path.join(self.run_dir, f"{prefix}_{idx:04d}.jsonl")

    def _write_batch(self, rows: List[Dict[str, Any]], final_path: str):
        tmp_path = final_path + config_module.config.storage.tmp_suffix
        try:
            with open(tmp_path, "w", encoding=config_module.config.storage.encoding) as f:
                for row in rows:
                    json.dump(row, f, ensure_ascii=False)
                    f.write("\n")
            os.replace(tmp_path, final_path)
        except Exception as e:
            logger.error(f"Failed batch write to {final_path}: {e}")
            # Cleanup tmp if failed
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
