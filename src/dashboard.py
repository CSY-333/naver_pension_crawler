import streamlit as st
import pandas as pd
import os
import time
import subprocess
import sys
from config import config

st.set_page_config(
    page_title="Naver News Pension Crawler Dashboard",
    page_icon="N",
    layout="wide",
)

st.title("Naver News Pension Crawler Dashboard")

# Paths logic handled safely (Config already updated to relative/home)
# But here we need to know where the output dir is.
# Config might have been loaded at import time, which is fine for UI display
try:
    if config.storage.output_dir.startswith("~"):
        OUTPUT_DIR = os.path.expanduser(config.storage.output_dir)
    else:
        OUTPUT_DIR = os.path.abspath(config.storage.output_dir)
except:
    OUTPUT_DIR = "GPR" # Fallback

ARTICLES_CSV = os.path.join(OUTPUT_DIR, config.storage.articles_filename)
COMMENTS_CSV = os.path.join(OUTPUT_DIR, config.storage.comments_filename)


def load_data():
    """Load data from CSVs safely."""
    articles = pd.DataFrame()
    comments = pd.DataFrame()

    if os.path.exists(ARTICLES_CSV):
        try:
            articles = pd.read_csv(ARTICLES_CSV, encoding=config.storage.encoding)
        except Exception as e:
            st.error(f"Error loading articles: {e}")

    if os.path.exists(COMMENTS_CSV):
        try:
            comments = pd.read_csv(COMMENTS_CSV, encoding=config.storage.encoding)
        except Exception as e:
            st.error(f"Error loading comments: {e}")

    return articles, comments


# Sidebar for controls
st.sidebar.header("Controls")
if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()

# Crawler Execution - Process Isolation
st.sidebar.subheader("Crawler Run")
headless_option = st.sidebar.checkbox("Headless mode", value=config.crawler.headless)
run_btn = st.sidebar.button("Run Crawler Now")

# State for running process
if "crawler_pid" not in st.session_state:
    st.session_state["crawler_pid"] = None

if run_btn:
    if st.session_state["crawler_pid"] is None:
        cmd = [sys.executable, "-m", "src.main"]
        if not headless_option:
            cmd.append("--no-headless")
        
        # Start subprocess
        try:
            # Popen allows us to not block the UI
            process = subprocess.Popen(
                cmd,
                cwd=os.getcwd(), # Ensure we run from root
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True # Python 3.7+
            )
            st.session_state["crawler_pid"] = process.pid
            st.success(f"Started crawler (PID: {process.pid})")
        except Exception as e:
            st.error(f"Failed to start crawler: {e}")
    else:
        st.warning("Crawler is already running!")

# Status check
if st.session_state["crawler_pid"]:
    st.info(f"Crawler is running (PID: {st.session_state['crawler_pid']})... Check logs for details.")
    # In a real app, we might check process.poll() here using psutil or similiar if we kept the object,
    # but separate requests lose the object. We only have PID.
    # For simple dashboard, we assume it runs. 
    # To Reset:
    if st.sidebar.button("Clear PID (Force Reset)"):
        st.session_state["crawler_pid"] = None
        st.rerun()

auto_refresh = st.sidebar.checkbox("Auto-refresh (10s)", value=True)

# Load Data
articles, comments = load_data()

# Metrics
col1, col2, col3, col4 = st.columns(4)

total_articles = len(articles) if not articles.empty else 0
total_comments = len(comments) if not comments.empty else 0

collected_articles_count = 0
if not articles.empty and "comments_collected" in articles.columns:
    try:
        collected_articles_count = articles["comments_collected"].astype(bool).sum()
    except:
        pass

col1.metric("Total Articles Scanned/Matched", f"{total_articles:,}")
col2.metric("Articles with Comments", f"{collected_articles_count:,}")
col3.metric("Total Comments Collected", f"{total_comments:,}")
col4.metric("Last Update", time.strftime("%H:%M:%S"))

# Charts
if not articles.empty:
    st.subheader("Collection Trends")
    if "collected_at_kst" in articles.columns:
        articles["collected_at_kst"] = pd.to_datetime(articles["collected_at_kst"], errors="coerce")
        # Just simple counts
        st.bar_chart(articles["collected_at_kst"].dt.hour.value_counts())
        st.caption("Articles by Hour")

    st.subheader("Demographic Insights (Avg)")
    demog_cols = ["male_ratio", "female_ratio", "age_10s", "age_20s", "age_30s", "age_40s", "age_50s", "age_60_plus"]

    valid_cols = [c for c in demog_cols if c in articles.columns]

    if valid_cols and "demographic_available" in articles.columns:
        # Filter for rows where demog is True
        try:
             valid_data = articles[articles["demographic_available"] == True][valid_cols]
             if not valid_data.empty:
                 avg_demog = valid_data.mean()
                 st.bar_chart(avg_demog)
        except:
             st.info("Error parsing demographic stats.")
    else:
        st.info("No demographic columns found.")

    st.subheader("Recent Articles")
    st.dataframe(articles.tail(10))
else:
    st.warning("No article data found. Please run the crawler.")

if not comments.empty:
    st.subheader("Recent Comments")
    st.dataframe(comments.tail(10))

# Auto refresh logic
if auto_refresh:
    time.sleep(10)
    st.rerun()
