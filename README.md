# Naver Pension Crawler 🕷️

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-Async-45ba4b?style=flat-square&logo=playwright&logoColor=white)
![Hugging Face](https://img.shields.io/badge/Hugging%20Face-KoELECTRA-FFD21E?style=flat-square&logo=huggingface&logoColor=black)
![License](https://img.shields.io/badge/License-MIT-grey.svg?style=flat-square)

## 📖 About

**Naver Pension Crawler** is a high-performance **async data engineering pipeline** designed to extract, refine, and analyze public opinion on **pension reform**. It bridges the gap between raw web data and actionable intelligence by combining a hybrid crawler with a state-of-the-art sentiment analysis model.

---

## 🏗️ Architecture

This project goes beyond simple scraping, implementing a robust **Data Engineering Pipeline** that ensures stability, scalability, and data integrity.

### 1. Data Pipeline Overview

From raw extraction to intelligence generation, the data flows through strict phases.

```mermaid
graph LR
    subgraph "Phase 1: Extraction"
        A[Naver News] -->|HTTP/Playwright| B(Raw HTML/JSON)
    end

    subgraph "Phase 2: Refinement"
        B --> C{Data Cleaner}
        C -->|Deduplication| D[Cleaned Data]
        C -->|Filtering| D
    end

    subgraph "Phase 3: Intelligence"
        D --> E[KoELECTRA Model]
        E --> F[Sentiment Labeled Data]
    end

    subgraph "Phase 4: Storage"
        F --> G[(Final JSONL Archive)]
    end

    style B fill:#f96,stroke:#333,stroke-width:2px,color:white
    style D fill:#6cf,stroke:#333,stroke-width:2px,color:black
    style F fill:#9f6,stroke:#333,stroke-width:2px,color:black
    style G fill:#fff,stroke:#333,stroke-width:2px,color:black
```

### 2. System Interaction (Sequence Diagram)

How the components interact asynchronously to ensure non-blocking performance.

```mermaid
sequenceDiagram
    autonumber
    participant DE as Data Engineer
    participant CE as Crawler Engine (Async)
    participant PW as Playwright (Browser)
    participant API as Naver Comment API
    participant SA as Sentiment Analyzer

    Note over DE, CE: 1. Collection Phase
    DE->>CE: Execute Collection Script
    CE->>PW: Request News Page (Demographics)
    PW-->>CE: Return Rendered HTML/Canvas

    loop Pagination
        CE->>API: Async Request (Batch Process)
        API-->>CE: Return JSON Stream
    end

    CE->>CE: Stream Save to JSONL

    Note over DE, SA: 2. Analysis Phase
    DE->>SA: Trigger Sentiment Analysis
    SA->>SA: Load KoELECTRA-v3 Model

    loop Streaming Batches
        SA->>SA: Tokenize & Inference (GPU/CPU)
        SA-->>DE: Append Result to Final Archive
    end
```

### 3. C4 Container Diagram

A high-level view of the system containers and their responsibilities.

```mermaid
C4Container
    title Container Diagram for Naver Pension Crawler System

    System_Boundary(c1, "Naver Pension Crawler System") {
        Container(crawlerEngine, "Crawler Engine", "Python, aiohttp", "Hybrid orchestration of HTTP/API calls.")
        Container(finalCollector, "Final Data Collector", "Python, Playwright", "Deep scraping engine for comprehensive data.")
        Container(sentimentAnalyzer, "Sentiment Analyzer", "PyTorch, KoELECTRA", "NLP engine for sentiment classification.")

        ContainerDb(finalStorage, "Data Archive", "JSONL Files", "Structured storage for 40k+ records.")
    }

    System_Ext(naverServices, "Naver Services", "News & Comment Ecosystem")
    System_Ext(hfHub, "Hugging Face Hub", "Model Repository")

    Rel(crawlerEngine, naverServices, "Scrapes")
    Rel(finalCollector, naverServices, "Deep Scrapes")
    Rel(sentimentAnalyzer, hfHub, "Downloads Model")
    Rel(sentimentAnalyzer, finalStorage, "Enriches Data")
```

---

## ⚡ Technical Highlights

### 🌊 Memory-Safe Streaming Processing

Processing **40,000+** comments requires efficient memory management. Unlike traditional "Bulk Loading" which can crash systems by loading all data into RAM, this project uses **Python Generators** to treat data as a continuous stream.

```mermaid
graph TD
    subgraph "⛔ Bulk Processing (Risky)"
        All[Load 4GB Data] -->|RAM Overflow| Crash(System Crash 💥)
    end

    subgraph "✅ Streaming (Optimized)"
        Stream[Input Stream] -->|Yield Line| Proc[Process 1 Record]
        Proc -->|Write| Save[Save to Disk]
        Save -->|Release Memory| Stream
    end

    style Crash fill:#ff6666,color:white
    style Save fill:#66ff66,color:black
```

> This ensures a **Constant Memory Footprint** regardless of dataset size.

### 🧠 Advanced Sentiment Analysis (KoELECTRA)

We utilize `koelectra-base-v3-generalized-sentiment-analysis`, a model fine-tuned on the NSMC dataset, specifically optimized for informal Korean text found in online comments.

```mermaid
graph TD
    Input[Comment: "연금 개혁 꼭 필요합니다!"] --> Tokenizer[KoELECTRA Tokenizer]
    Tokenizer -->|Encoding| Model[Pre-trained KoELECTRA-v3]
    Model -->|Feature Extraction| Classifier[Linear Layer]
    Classifier -->|Softmax| Output{Positive: 98.7%}

    style Input fill:#fff,stroke:#333
    style Output fill:#ffe,stroke:#f66,stroke-width:2px
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- `pip` & `git`

### Installation

```bash
git clone https://github.com/CSY-333/naver_pension_crawler.git
cd naver_pension_crawler
pip install -r requirements.txt
playwright install
```

### Usage

**1. Collect Data**

```bash
py src/collect_final_data.py
```

**2. Analyze Sentiment**

```bash
py src/analyze_sentiment.py
```

---

## 🛠️ Tech Stack

| Category     | Technology                                |
| ------------ | ----------------------------------------- |
| **Language** | Python 3.11                               |
| **Crawling** | `aiohttp`, `Playwright`, `BeautifulSoup4` |
| **Data Eng** | `Pandas`, JSONL (Streaming)               |
| **AI / ML**  | `Hugging Face Transformers`, `PyTorch`    |
| **Model**    | KoELECTRA-Base-v3 (Generalized Sentiment) |

## 📜 License

This project is licensed under the MIT License.
