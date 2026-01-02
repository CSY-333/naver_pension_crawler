import json
import os
import glob
from datetime import datetime
from tqdm import tqdm
from transformers import pipeline
import torch

def get_latest_comments_file(directory):
    files = glob.glob(os.path.join(directory, "final_comments_*.jsonl"))
    if not files:
        return None
    # Sort by modification time, newest first
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]

def analyze_sentiment():
    input_dir = "GPR_FINAL"
    input_file = get_latest_comments_file(input_dir)
    
    if not input_file:
        print("No comments file found in GPR_FINAL")
        return

    print(f"Analyzing sentiment for file: {input_file}")
    
    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"final_comments_sentiment_{timestamp}.jsonl"
    output_path = os.path.join(input_dir, output_filename)
    
    print("Loading model... (this may take a while first time)")
    # Check if GPU is available
    device = 0 if torch.cuda.is_available() else -1
    print(f"Using device: {'GPU' if device == 0 else 'CPU'}")
    
    try:
        sentiment_analyzer = pipeline(
            "sentiment-analysis", 
            model="jaehyeong/koelectra-base-v3-generalized-sentiment-analysis",
            device=device
        )
    except Exception as e:
        print(f"Error loading model: {e}")
        return

    total_lines = sum(1 for _ in open(input_file, 'r', encoding='utf-8'))
    
    print(f"Processing {total_lines} comments...")
    
    with open(input_file, 'r', encoding='utf-8') as f_in, \
         open(output_path, 'w', encoding='utf-8') as f_out:
        
        for line in tqdm(f_in, total=total_lines):
            if not line.strip():
                continue
                
            try:
                data = json.loads(line)
                # content key is 'comment_text' in the saved json
                content = data.get('comment_text', '') or data.get('contents', '')
                content = content.strip()
                
                if content:
                    # Truncate if too long (model limit usually 512 tokens, safe bet ~1000 chars)
                    # The pipeline handles truncation but explicitly shortening can save time/errors
                    truncated_content = content[:512] 
                    
                    result = sentiment_analyzer(truncated_content)[0]
                    # Result is like {'label': 'positive', 'score': 0.99} or numbers
                    # monologg model outputs labels: '0' (negative), '1' (positive) usually, let's verify map
                    
                    # Map labels if necessary (standard nsmc models uses 'negative'/'positive' or '0'/'1')
                    label = result['label']
                    score = result['score']
                    
                    data['sentiment_label'] = label
                    data['sentiment_score'] = score
                else:
                    data['sentiment_label'] = None
                    data['sentiment_score'] = None
                    
                f_out.write(json.dumps(data, ensure_ascii=False) + '\n')
                
            except Exception as e:
                print(f"Error processing line: {e}")
                continue
                
    print(f"Sentiment analysis completed. Saved to {output_path}")

if __name__ == "__main__":
    analyze_sentiment()
