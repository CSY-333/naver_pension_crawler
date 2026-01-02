from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Test URL (May 23 2025)
        url = "https://search.naver.com/search.naver?where=news&query=%EA%B5%AD%EB%AF%BC%EC%97%B0%EA%B8%88&sm=tab_opt&sort=1&photo=0&field=0&pd=3&ds=2025.05.23&de=2025.05.23"
        
        print(f"Goto: {url}")
        page.goto(url)
        page.wait_for_load_state("networkidle")
        
        # Check "a.info"
        count_info = page.locator("a.info").count()
        print(f"Count a.info: {count_info}")
        
        # Check all links with "네이버뉴스"
        count_text = page.locator("a:has-text('네이버뉴스')").count()
        print(f"Count text='네이버뉴스': {count_text}")
        
        # Get class names of first 5 links
        links = page.query_selector_all("a")
        print("\nTop 10 Link Classes:")
        for i, link in enumerate(links[:20]):
            txt = link.inner_text().strip()
            cls = link.get_attribute("class")
            href = link.get_attribute("href")
            if txt or "news.naver" in (href or ""):
                print(f"[{i}] Text: {txt[:20]} | Class: {cls} | Href: {href}")

        # Dump HTML
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(page.content())
            
        browser.close()

if __name__ == "__main__":
    run()
