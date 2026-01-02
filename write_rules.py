import os

content = """# Project Development Rules

This document outlines the engineering standards for the Naver News Pension Crawler project.

## 1. Core Philosophy: Pragmatic TDD & SOLID

### 1.1 TDD Strategy (Context-Dependent)
*   **Pure Logic (Mandatory TDD)**: Core utilities, parsers, and data transformations (e.g., `extract_oid`, `parse_date`) must have unit tests written *first*.
*   **Interactions (Smoke Tests)**: Scraper selectors and navigational logic do not require strict TDD but must have integration/smoke tests to verify connectivity.

### 1.2 SOLID Guidelines
*   **[S] SRP (Mandatory)**: Modules/Classes must have a single responsibility.
*   **[D/O] Extensibility (Guideline)**: Apply Open/Closed and Dependency Inversion only when clear extension points are needed (e.g., pluggable Exporters). Do not over-engineer simple scripts.

---

## 2. Operational Stability (Non-Negotiable)

*   **Data Persistence**:
    *   **Policy**: Data must be saved via **Incremental Append** OR **Buffered Flush** (e.g., every N items or T seconds).
    *   **Prohibited**: Relying solely on "bulk save at the end".
*   **Crash Recovery**:
    *   Global error handling must log exceptions with context (URL/Payload) and *continue* the loop.
    *   **Prohibited**: `except: pass` (Silent failures).
*   **Run Partitioning**:
    *   Every execution must have a unique `run_id` and isolated output directory.
    *   **Config Snapshot**: Copy `config.yaml` to the run directory at startup.

## 3. Environment & Integrity

*   **Path Independence**: Use relative paths (`./output`) or config-defined roots. **Absolute user paths are forbidden.**
*   **File Formats**:
    *   **JSONL (Mandatory)**: For high-volume text data (Comments, Article Bodies).
    *   **CSV (Allowed)**: For headers, metadata tables, or summary stats.
*   **Encoding**: Always `utf-8`.

## 4. Performance & Networking

*   **Async Policy**:
    *   **Heavy I/O (Async Required)**: High-volume scraping (e.g., Pagination loops) must use `aiohttp` / `asyncio`.
    *   **Light I/O (Sync Allowed)**: Initial search or single-page checks can use synchronous requests/selenium if robust.
    *   **Prohibited**: `time.sleep()` in main loops (blocker). Use `asyncio.sleep` or non-blocking waits.
*   **Safety Limits**:
    *   **Concurrency**: Must be capped with `Semaphore` (e.g., max 20).
    *   **Retries**: Finite retries with exponential backoff (Max 3-5). **Infinite loops are forbidden.**

## 5. Observability & Ethics

*   **Metrics**: Logs must track `run_id`, `scanned_count`, `success_count`, `error_rate`, and `fallback_usage`.
*   **Ethics**: Respect `robots.txt` where feasible. Default concurrency settings should be conservative to avoid DOS behavior.
"""

os.makedirs(".agent/rules", exist_ok=True)
with open(".agent/rules/rules.md", "w", encoding="utf-8") as f:
    f.write(content)
print("Rules updated successfully.")
