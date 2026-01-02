import sys
import os
import asyncio
import argparse
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

# Add repo root to path to allow running as script from other locations
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ensure Windows event loop supports subprocesses (needed for Playwright)
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from src import config as config_module
from src.config import Config
from src.crawler import NaverNewsCrawler
from src.storage import CSVExporter
from src.report import ReportGenerator
from src.lock import RunLock

def setup_logging(run_id: str):
    """Configure logging to file and console."""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"run_{run_id}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,  # override any existing handlers (e.g., streamlit)
    )

def get_kst_time():
    """Get current time in KST."""
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).isoformat()


def load_config(config_path: Optional[str] = None) -> Config:
    """Load config and refresh the shared module instance."""
    cfg = Config.load(config_path or "config/config.yaml")
    config_module.config = cfg
    return cfg


async def run_pipeline(headless: Optional[bool] = True, run_id: Optional[str] = None, config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Run the crawler pipeline. Designed for reuse from Streamlit or CLI.

    Args:
        headless: Whether to run Playwright headless. If None, keep current config value.
        run_id: Optional explicit run identifier.

    Returns:
        dict with run metadata and stats.
    """
    # Load / refresh config each run so Streamlit + CLI stay in sync
    cfg = load_config(config_path)

    # Allow callers to override headless mode dynamically
    if headless is not None:
        cfg.crawler.headless = bool(headless)

    run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    setup_logging(run_id)
    logger = logging.getLogger("main")

    logger.info(f"Initialized Run ID: {run_id}")



    # Run pipeline
    # Determine lock directory (Project Root or Output Dir?)
    # PRD said GPR/.run.lock. GPR is config.storage.output_dir
    
    # Handle path expansion for lock dir
    lock_dir = cfg.storage.output_dir
    if lock_dir.startswith("~"):
        lock_dir = os.path.expanduser(lock_dir)
    else:
        lock_dir = os.path.abspath(lock_dir)
        
    # Ensure dir exists for lock
    if not os.path.exists(lock_dir):
        os.makedirs(lock_dir, exist_ok=True)

    locker = RunLock(lock_dir)
    
    try:
        with locker.acquire():
            logger.info("Pipeline lock acquired.")
            logger.info(f"Initialized Run ID: {run_id}")

            # Init components
            crawler = NaverNewsCrawler(run_id=run_id)
            # exporter = CSVExporter() # Unused, crawler handles it
            reporter = ReportGenerator(run_id)

            # Run pipeline
            articles, comments = await crawler.run()

            # Post-process: Add Metadata
            collected_at = get_kst_time()

            for art in articles:
                art["run_id"] = run_id
                art["collected_at_kst"] = collected_at

            for cmt in comments:
                cmt["run_id"] = run_id

            # Export (Saved incrementally by crawler, so we don't need bulk export here)
            # exporter.export_articles(articles)
            # exporter.export_comments(comments)

            # Report
            reporter.set_stats(crawler.stats)
            report_path = reporter.generate()

            logger.info("Pipeline completed successfully.")

            return {
                "run_id": run_id,
                "articles": len(articles),
                "comments": len(comments),
                "stats": crawler.stats,
                "report_path": report_path,
                "collected_at_kst": collected_at,
            }
            
    except RuntimeError as e:
        logger.error(f"Pipeline locked: {e}")
        # Re-raise to let caller know
        raise e
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        raise e


def cli():
    """CLI entry point that mirrors previous behavior."""
    parser = argparse.ArgumentParser(description="Naver News Pension Crawler")
    parser.add_argument("--config", help="Path to custom config.yaml")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--no-headless", action="store_false", dest="headless", help="Run in visible mode")
    parser.set_defaults(headless=True)

    args = parser.parse_args()

    try:
        asyncio.run(run_pipeline(headless=args.headless, config_path=args.config))
    except Exception:
        # Let logging capture full traceback, but ensure non-zero exit for CLI callers
        logging.exception("Fatal error in main pipeline")
        sys.exit(1)


if __name__ == "__main__":
    cli()
