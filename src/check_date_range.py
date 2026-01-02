
import json
import os
import glob
from datetime import datetime, timedelta
import re
import sys

# Ensure UTF-8 output for Windows console
sys.stdout.reconfigure(encoding='utf-8')

def parse_relative_date(date_str, collected_at):
    """
    Parses relative dates like '1시간 전', '2일 전' into YYYY-MM-DD.
    Falls back to parsing 'YYYY.MM.DD' if absolute.
    """
    if not date_str or date_str == "Unknown Date":
        return None

    try:
        # 1. Absolute Date (YYYY.MM.DD)
        if re.match(r"\d{4}\.\d{2}\.\d{2}", date_str):
            return datetime.strptime(date_str.split(" ")[0], "%Y.%m.%d").date()

        # 2. Relative Date
        collected_date = datetime.fromisoformat(collected_at).date() if collected_at else datetime.now().date()
        
        if "분 전" in date_str:
            return collected_date # Treat as today
        elif "시간 전" in date_str:
            hours_match = re.search(r"(\d+)", date_str)
            if hours_match:
                hours = int(hours_match.group(1))
                collected_dt = datetime.fromisoformat(collected_at)
                article_dt = collected_dt - timedelta(hours=hours)
                return article_dt.date()
            return collected_date
        elif "일 전" in date_str:
            days_match = re.search(r"(\d+)", date_str)
            if days_match:
                days = int(days_match.group(1))
                return collected_date - timedelta(days=days)
            return collected_date
        elif "주 전" in date_str:
              weeks_match = re.search(r"(\d+)", date_str)
              if weeks_match:
                  weeks = int(weeks_match.group(1))
                  return collected_date - timedelta(weeks=weeks)
              return collected_date
        else:
            return None
            
    except Exception as e:
        # print(f"Error parsing date '{date_str}': {e}")
        return None

def check_range():
    # Use relative path from current working directory
    base_dir = os.path.join("GPR_2025_HQ", "run_20260101_182515")
    search_pattern = os.path.join(base_dir, "articles_batch_*.jsonl")
    
    print(f"Searching for files in: {search_pattern}")
    files = glob.glob(search_pattern)
    
    print(f"Scanning {len(files)} files...")
    
    dates = []
    
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as f_in:
                for line in f_in:
                    if not line.strip(): continue
                    try:
                        item = json.loads(line)
                        pub = item.get("published_at")
                        collected = item.get("collected_at_kst")
                        
                        date_obj = parse_relative_date(pub, collected)
                        if date_obj:
                            dates.append(date_obj)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error reading file {f}: {e}")
    
    if not dates:
        print("No valid dates found.")
        return

    min_date = min(dates)
    max_date = max(dates)
    
    print(f"Total Valid Dates: {len(dates)}")
    print(f"Date Range: {min_date} ~ {max_date}")
    
    # Optional: Distribution
    from collections import Counter
    c = Counter(dates)
    print("\nDate Distribution:")
    sorted_dates = sorted(c.keys())
    
    # Print first 5 and last 5 if too many
    if len(sorted_dates) > 10:
        for d in sorted_dates[:5]:
            print(f"{d}: {c[d]} articles")
        print("...")
        for d in sorted_dates[-5:]:
            print(f"{d}: {c[d]} articles")
    else:
        for d in sorted_dates:
            print(f"{d}: {c[d]} articles")

if __name__ == "__main__":
    check_range()
