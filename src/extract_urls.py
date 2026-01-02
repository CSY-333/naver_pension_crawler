import os
import json
import glob
import argparse
import logging
from datetime import datetime
from typing import List, Set, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

DEFAULT_DIRS = [
    "GPR", 
    "GPR_2025", 
    "GPR_2025_HQ", 
    "GPR_IMPACT_URLS", 
    "GPR_IMPACT_FULL"
]

def extract_all_urls(base_dirs: List[str], output_file: str, verbose: bool = False):
    if verbose:
        logger.setLevel(logging.DEBUG)
    
    seen_urls: Set[str] = set()
    total_count = 0
    duplicate_count = 0
    
    logger.info(f"Scanning directories: {base_dirs}")
    
    # Ensure output directory exists
    out_dir = os.path.dirname(os.path.abspath(output_file))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as out_f:
        for base_dir in base_dirs:
            if not os.path.exists(base_dir):
                logger.warning(f"Directory not found: {base_dir}")
                continue
            
            logger.info(f"Scanning {base_dir}...")
            
            # Recursive search for articles_batch*.jsonl
            # Use glob with recursive=True
            pattern = os.path.join(base_dir, "**", "articles_batch*.jsonl")
            files = glob.glob(pattern, recursive=True)
            
            if not files:
                logger.debug(f"No article files found in {base_dir}")
                continue
                
            for file_path in files:
                logger.debug(f"Reading {file_path}...")
                
                # Extract simple run_id from filename or path if possible
                # e.g. .../run_20250101_.../articles_batch_...jsonl
                # Try to find 'run_' in path parts
                parts = os.path.normpath(file_path).split(os.sep)
                run_id_guess = "unknown"
                for part in parts:
                    if part.startswith("run_"):
                        run_id_guess = part
                        break
                
                try:
                    with open(file_path, "r", encoding="utf-8") as in_f:
                        for line_num, line in enumerate(in_f, 1):
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                data = json.loads(line)
                                url = data.get("url")
                                
                                if url:
                                    if url not in seen_urls:
                                        seen_urls.add(url)
                                        
                                        # Metadata object
                                        meta = {
                                            "url": url,
                                            "source_file": file_path,
                                            "run_id": run_id_guess,
                                            "extracted_at": datetime.now().isoformat()
                                        }
                                        
                                        out_f.write(json.dumps(meta, ensure_ascii=False) + "\n")
                                        total_count += 1
                                    else:
                                        duplicate_count += 1
                                        
                            except json.JSONDecodeError as e:
                                logger.warning(f"JSON Error in {file_path}:{line_num} - {e}")
                except Exception as e:
                    logger.error(f"Failed to read file {file_path}: {e}")

    logger.info(f"Extraction complete.")
    logger.info(f"Total unique URLs: {total_count}")
    logger.info(f"Duplicates skipped: {duplicate_count}")
    logger.info(f"Saved to: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract all unique URLs from crawler output directories.")
    parser.add_argument("--dirs", nargs="+", default=DEFAULT_DIRS, help="List of base directories to scan.")
    parser.add_argument("--output", type=str, default="all_collected_urls.jsonl", help="Output JSONL filename.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging.")
    
    args = parser.parse_args()
    
    extract_all_urls(args.dirs, args.output, args.verbose)
