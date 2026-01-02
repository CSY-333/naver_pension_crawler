import json
import os
import logging
from typing import Dict, Any, List
from datetime import datetime
from .config import config

logger = logging.getLogger(__name__)

class ReportGenerator:
    """Generates execution summary reports."""
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.start_time = datetime.now()
        self.stats = {}
    
    def set_stats(self, stats: Dict[str, Any]):
        self.stats = stats
        
    def generate(self):
        """Create and save the run report."""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        report = {
            "run_id": self.run_id,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "stats": self.stats,
            "config": {
                "keywords": config.search.keywords,
                "max_pages": config.search.max_pages,
                "threshold": config.filters.comment_threshold
            }
        }
        
        # Save to logs dir
        filename = f"summary_{self.run_id}.json"
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        path = os.path.join(log_dir, filename)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Run summary saved to {path}")
        return path
