# Architecture Decision Records (ADR)

## ADR-001: Hybrid Crawling Strategy

### Status

Accepted

### Context

We needed to collect data from Naver News, which serves content via both server-side rendering (SSR) and client-side dynamic loading (CSR).

- **Search Results**: Accessible via HTTP requests but blocked significantly when using high-frequency requests.
- **Article Details**: Static HTML content.
- **Demographics & Comments**: Loaded dynamically via Javascript/API.

### Decision

We adopted a **Hybrid Strategy**:

1.  **HTTP/API First**: Use `aiohttp` for search results and comment APIs. This is orders of magnitude faster than browser automation.
2.  **Playwright Fallback**: Use `Playwright` (headless browser) only for:
    - Demographic charts (Canvas/JS extraction).
    - When HTTP requests trigger bot detection (403 Forbidden).

### Consequences

- **Pros**: Speed is maximized for the 90% of data (comments/text) obtainable via API. Reliability is ensured via browser fallback.
- **Cons**: Complexity in managing two different session types (aiohttp session vs Playwright context).

---

## ADR-002: Korean Sentiment Analysis Model Selection

### Status

Accepted

### Context

We need to classify the sentiment (positive/negative) of user comments related to pension reform. The data is informal Korean text (internet comments).

### Decision

We selected **KoELECTRA** (specifically `jaehyeong/koelectra-base-v3-generalized-sentiment-analysis`).

- **Reason 1**: ELECTRA pre-training objective (Replaced Token Detection) is more efficient and effective for smaller datasets than BERT.
- **Reason 2**: The specific model is fine-tuned on NSMC (Naver Sentiment Movie Corpus) and other datasets, making it robust for informal Korean text.
- **Reason 3**: `kiyoungkim1/LMkor` was considered but required additional fine-tuning. We opted for an immediately usable fine-tuned model for the MVP.

### Consequences

- **Pros**: High accuracy on zero-shot inference for comments.
- **Cons**: Inference on CPU is relatively slow (approx 15-20 iterations/sec), requiring GPU for large-scale production.

---

## ADR-003: Asynchronous Concurrency with Semaphores

### Status

Accepted

### Context

Crawling thousands of articles involves heavy I/O waiting. Uncontrolled concurrency leads to IP bans (429/403 errors).

### Decision

We implemented **`asyncio` with `Semaphores`**.

- `article_sem` (default 5): Limits concurrent article processing.
- `page_sem` (default 10): Limits concurrent API pagination requests.

### Consequences

- **Pros**: Maximizes network utilization without overwhelming the target server.
- **Cons**: Debugging async code is improved but stack traces can be complex.
