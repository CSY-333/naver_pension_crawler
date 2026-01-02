# Naver News Pension Crawler

A robust web crawler for collecting Naver News articles about "국민연금" (National Pension) from sections 100 (Politics), 101 (Economy), and 102 (Society). It collects article metadata, comments (for high-engagement articles), and demographic summaries.

## Features

- **Targeted Crawling**: Scans specific Naver News sections.
- **Filtering**: Filters articles by keywords ("국민연금", "국민 연금").
- **Comment Collection**: Collects comments if count >= 100.
- **Demographics**: Extracts gender and age distribution for articles.
- **Polite Crawling**: Random delays and user-agent rotation.
- **Robustness**: Handles network errors and UI variations.
- **Data Export**: Saves to CSV (UTF-8 BOM for Excel).

## Prerequisites

- Python 3.11+
- Playwright

## Installation

1. Create a virtual environment (optional but recommended):

   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Install Playwright browsers:
   ```powershell
   playwright install chromium
   ```

## 📜 Project Rules

This project follows strict engineering standards defined in [.agent/rules/rules.md](.agent/rules/rules.md).
**Core principles:**

1. **TDD & SOLID**: All code must comprise unit tests and follow modular design.
2. **Operational Stability**: Incremental saving and crash recovery are mandatory.
3. **Async First**: Prefer `aiohttp` for network operations.

## Usage

### standard Run

Run the crawler using the provided batch script:

```powershell
.\crawl.bat
```

Or directly via Python:

```powershell
python src/main.py
```

### Configuration

Edit `config/config.yaml` to change parameters:

- `articles_per_section`: Number of articles to scan per section.
- `comment_threshold`: Minimum comments to trigger collection.
- `keywords`: List of title keywords to filter by.
- `headless`: Set to `false` to see the browser while crawling.

### Output

Data is saved to `C:/Users/maudi/OneDrive/문서/GPR/`:

- `articles_pension.csv`: Article metadata and demographics.
- `comments_pension.csv`: Collected comments.

Logs and run summaries are saved in `logs/`.

## Project Structure

```
naver_pension_crawler/
├── config/             # Configuration files
├── logs/               # Run logs and JSON summaries
├── src/                # Source code
│   ├── crawler.py      # Main crawler logic
│   ├── parsers.py      # HTML parsing logic
│   ├── selectors.py    # CSS selectors
│   ├── storage.py      # CSV export logic
│   ├── report.py       # Reporting module
│   └── main.py         # Entry point
├── tests/              # Tests
├── requirements.txt    # Dependencies
├── crawl.bat           # Execution script
└── README.md           # Documentation
```
