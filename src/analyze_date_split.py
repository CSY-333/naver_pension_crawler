
import os
import json
import random
from typing import List, Dict, Any
from datetime import datetime

TARGET_DATE = datetime(2025, 3, 20)
BASE_DIR = r"c:\Users\maudi\OneDrive\문서\test\naver_pension_crawler\GPR_2025_HQ\run_20260101_161400"

def parse_korean_date(date_str: str) -> datetime:
    """
    Parses '2025.03.20. 오전 11:22' or '2025.03.20.' format.
    """
    try:
        # Remove period at end if exists
        date_str = date_str.strip()
        if date_str.endswith("."):
            date_str = date_str[:-1]
        
        # Only take the YYYY.MM.DD part
        parts = date_str.split(".")
        if len(parts) >= 3:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2].split(" ")[0])
            return datetime(year, month, day)
    except Exception as e:
        pass
    return None

def analyze():
    articles_pre = []
    articles_post = []
    
    # 1. Load Articles
    print("Loading articles...")
    article_map = {} # url -> date_bucket
    
    for filename in os.listdir(BASE_DIR):
        if filename.startswith("articles_batch") and filename.endswith(".jsonl"):
            path = os.path.join(BASE_DIR, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        data = json.loads(line)
                        url = data.get("url")
                        date_str = data.get("published_at", "")
                        
                        dt = parse_korean_date(date_str)
                        if dt:
                            if dt < TARGET_DATE:
                                articles_pre.append(data)
                                article_map[url] = "PRE"
                            else:
                                articles_post.append(data)
                                article_map[url] = "POST"
            except Exception as e:
                print(f"Error reading {filename}: {e}")

    print(f"Articles Pre-3/20: {len(articles_pre)}")
    print(f"Articles Post-3/20: {len(articles_post)}")

    # 2. Load Comments
    print("Loading comments...")
    comments_pre = []
    comments_post = []
    
    for filename in os.listdir(BASE_DIR):
        if filename.startswith("comments_batch") and filename.endswith(".jsonl"):
            path = os.path.join(BASE_DIR, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        data = json.loads(line)
                        url = data.get("article_url") # or check how it's linked
                        # If url not in data, try 'url' field if it exists in schema
                        
                        bucket = article_map.get(url)
                        if bucket == "PRE":
                            comments_pre.append(data.get("contents", ""))
                        elif bucket == "POST":
                            comments_post.append(data.get("contents", ""))
            except Exception as e:
                print(f"Error reading {filename}: {e}")

    print(f"Comments Pre-3/20: {len(comments_pre)}")
    print(f"Comments Post-3/20: {len(comments_post)}")
    
    # 3. Sample
    sample_size = 5
    print("\n--- SAMPLE PRE-3/20 ---")
    for c in random.sample(comments_pre, min(len(comments_pre), sample_size)):
        print(f"- {c[:100]}...")

    print("\n--- SAMPLE POST-3/20 ---")
    for c in random.sample(comments_post, min(len(comments_post), sample_size)):
        print(f"- {c[:100]}...")

if __name__ == "__main__":
    analyze()
