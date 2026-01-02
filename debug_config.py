
try:
    from src import config
    print("Config imported successfully")
    print(f"Only URLs default: {config.config.crawler.only_urls}")
except Exception as e:
    print(f"Import failed: {e}")
