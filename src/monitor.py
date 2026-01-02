import json
import os
import time
from typing import Dict, Any

class StatusMonitor:
    """
    Writes status.json to the run directory for monitoring.
    """
    def __init__(self, run_dir: str):
        self.status_file = os.path.join(run_dir, "status.json")
        self.status = {
            "stage": "INIT",
            "last_updated": time.time(),
            "keyword": None,
            "scanned": 0,
            "collected": 0,
            "errors_count": 0
        }
        self.update()

    def update_stats(self, crawler_stats: Dict[str, Any]):
        """Update from crawler stats object."""
        self.status["scanned"] = crawler_stats.get("scanned", 0)
        self.status["collected"] = crawler_stats.get("collected", 0)
        self.status["errors_count"] = len(crawler_stats.get("errors", []))
        self.update()

    def set_stage(self, stage: str):
        self.status["stage"] = stage
        self.update()
        
    def set_keyword(self, keyword: str):
        self.status["keyword"] = keyword
        self.update()

    def update(self):
        self.status["last_updated"] = time.time()
        try:
            with open(self.status_file, "w", encoding="utf-8") as f:
                json.dump(self.status, f, ensure_ascii=False, indent=2)
        except Exception:
            pass # Non-critical
