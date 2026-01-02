# Naver Pension Crawler 🕷️

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-Async-45ba4b?style=flat-square&logo=playwright&logoColor=white)
![Hugging Face](https://img.shields.io/badge/Hugging%20Face-Transformers-FFD21E?style=flat-square&logo=huggingface&logoColor=black)
![License](https://img.shields.io/badge/License-MIT-grey.svg?style=flat-square)

## About

A high-performance asynchronous crawler designed to collect and analyze public opinion on **pension reform** from Naver News comments, featuring demographic data extraction and sentiment analysis.

## Key Features

- 🚀 **Hybrid Crawling Engine**: Intelligently switches between high-speed HTTP/API calls and headless browser (Playwright) to bypass bot protections and render dynamic JS content.
- 💬 **Massive Comment Collection**: capable of harvesting unlimited comments per article using the specialized Naver Comment API.
- 📊 **Demographic Extraction**: Scrapes age and gender distribution charts from news articles to contextualize public opinion.
- 🧠 **Sentiment Analysis**: Integrated **KoELECTRA** model to automatically classify Korean comments into Positive/Negative sentiments with confidence scores.
- 🛡️ **Robust Error Handling**: Implements exponential backoff, user-agent rotation, and semaphore-based concurrency control to respect rate limits.

## Architecture

### System Context (Level 1)

The system acts as a bridge between raw Naver News data and the Data Engineer, enriching the data with sentiment intelligence.

```mermaid
C4Context
    title System Context Diagram for Naver Pension Crawler

    Person(dataEngineer, "Data Engineer", "Configures crawler, runs scripts, and analyzes collected data.")

    System(crawlerSystem, "Naver Pension Crawler System", "Collects news articles, comments, and demographic statistics related to pension reform.")

    System_Ext(naverNews, "Naver News", "Provides news articles and search functionality.")
    System_Ext(naverCommentAPI, "Naver Comment API", "Provides user comments and social statistics.")
    System_Ext(playwright, "Playwright Browser", "Headless browser for rendering dynamic content (charts, JS).")
    System_Ext(hfModels, "Hugging Face Models", "Provides pre-trained NLP models for sentiment analysis.")

    Rel(dataEngineer, crawlerSystem, "Configures & Executes", "CLI / Scripts")
    Rel(crawlerSystem, naverNews, "Crawls / Scrapes", "HTTP Request / HTML")
    Rel(crawlerSystem, naverCommentAPI, "Fetches API Data", "JSONP/HTTP")
    Rel(crawlerSystem, playwright, "Controls", "DevTools Protocol")
    Rel(crawlerSystem, hfModels, "Downloads & Uses", "Python Library")
    Rel(crawlerSystem, dataEngineer, "Delivers Data", "JSONL Files")
```

### Containers (Level 2)

The system is modularized into efficient Python containers for separation of concerns.

```mermaid
C4Container
    title Container Diagram for Naver Pension Crawler System

    Person(dataEngineer, "Data Engineer", "Operates the system")

    System_Boundary(c1, "Naver Pension Crawler System") {
        Container(crawlerEngine, "Crawler Engine", "Python, aiohttp", "Orchestrates searching and initial parsing of news articles.")
        Container(finalCollector, "Final Data Collector", "Python, Playwright", "Deep scraping of filtered URLs for comprehensive comment & demographic data.")
        Container(sentimentAnalyzer, "Sentiment Analyzer", "Python, KoELECTRA, PyTorch", "Performs batch sentiment analysis on collected comments.")

        ContainerDb(rawStorage, "Raw Data Storage", "JSONL Files", "Stores initial crawl results (articles, comments snippet).")
        ContainerDb(finalStorage, "Final Data Storage", "JSONL Files", "Stores complete dataset including unlimited comments and sentiment scores.")
        ContainerDb(modelCache, "Model Cache", "Local File System", "Cached Hugging Face pre-trained models.")
    }

    System_Ext(naverServices, "Naver Services", "News Search, Article Pages, Comment API")
    System_Ext(hfHub, "Hugging Face Hub", "Model Repository")

    Rel(dataEngineer, crawlerEngine, "Runs search crawler")
    Rel(dataEngineer, finalCollector, "Runs final collection")
    Rel(dataEngineer, sentimentAnalyzer, "Runs sentiment analysis")

    Rel(crawlerEngine, naverServices, "Search & Scraping", "HTTP/HTTPS")
    Rel(crawlerEngine, rawStorage, "Saves intermediate data", "JSONL")

    Rel(finalCollector, rawStorage, "Reads target URLs")
    Rel(finalCollector, naverServices, "Deep Scraping (API + Browser)", "HTTPS")
    Rel(finalCollector, finalStorage, "Saves complete data", "JSONL")

    Rel(sentimentAnalyzer, finalStorage, "Reads comments & Appends score", "JSONL")
    Rel(sentimentAnalyzer, hfHub, "Downloads model", "HTTPS")
    Rel(sentimentAnalyzer, modelCache, "Caches model", "File I/O")
```

👉 **For more detailed architectural decisions, please refer to the [ADR Records](docs/ADR.md).**

## Getting Started

### Prerequisites

- Python 3.10+
- Chrome/Chromium (installed via Playwright)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/CSY-333/naver_pension_crawler.git
cd naver_pension_crawler

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install browser binaries
playwright install
```

### Usage

1.  **Collect Data**:

    ```bash
    # Run the final data collection script
    py src/collect_final_data.py
    ```

    This will read URLs from `GPR_URLS/stats_urls.jsonl` and save results to `GPR_FINAL/`.

2.  **Analyze Sentiment**:
    ```bash
    # Run the sentiment analysis script
    py src/analyze_sentiment.py
    ```
    This processes the latest comment file in `GPR_FINAL/` and appends sentiment labels.

## Data Example

### Input (URL List)

```json
{
  "url": "https://n.news.naver.com/...",
  "date": "2024.01.01",
  "keyword": "국민연금"
}
```

### Output (Sentiment Analyzed Comment)

```json
{
  "comment_id": "123456789",
  "comment_text": "연금 개혁 반드시 필요합니다.",
  "author": "user****",
  "sentiment_label": "1",
  "sentiment_score": 0.9876
}
```

- `sentiment_label`: `1` (Positive), `0` (Negative)

## Tech Stack

- **Language**: Python 3.11
- **Crawling**: `aiohttp` (Async HTTP), `playwright` (Browser Automation), `beautifulsoup4`
- **NLP / ML**: `transformers` (Hugging Face), `torch` (PyTorch)
- **Model**: [jaehyeong/koelectra-base-v3-generalized-sentiment-analysis](https://huggingface.co/jaehyeong/koelectra-base-v3-generalized-sentiment-analysis)
- **Data**: JSONL (JSON Lines) for efficient large-scale storage
