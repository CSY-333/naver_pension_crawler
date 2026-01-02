import json
import os
import glob

def check_data():
    files = glob.glob(os.path.join("GPR_FINAL", "final_comments_*.jsonl"))
    # Filter out sentiment files
    files = [f for f in files if "sentiment" not in f]
    files.sort(key=os.path.getmtime, reverse=True)
    
    if not files:
        print("No input file found")
        return

    target = files[0]
    print(f"Checking {target}")
    
    total = 0
    empty = 0
    non_empty = 0
    
    with open(target, 'r', encoding='utf-8') as f:
        for line in f:
            total += 1
            try:
                data = json.loads(line)
                if not data.get('contents', '').strip():
                    empty += 1
                else:
                    non_empty += 1
            except:
                pass
                
    print(f"Total: {total}")
    print(f"Empty contents: {empty}")
    print(f"Non-empty contents: {non_empty}")

if __name__ == "__main__":
    check_data()
