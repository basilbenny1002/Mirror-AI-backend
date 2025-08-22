from playwright.sync_api import sync_playwright
import json, os

def crawl_js(base_url, max_pages=20, output_dir="scraped_data"):
    os.makedirs(output_dir, exist_ok=True)
    visited = set()
    to_visit = [base_url]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        while to_visit and len(visited) < max_pages:
            url = to_visit.pop()
            if url in visited:
                continue
            visited.add(url)

            try:
                page.goto(url, timeout=20000, wait_until="networkidle")
                content = page.content()
                title = page.title()
            except Exception as e:
                print(f" Failed {url}: {e}")
                continue

            # Extract visible text
            text = page.inner_text("body")

            data = {
                "url": url,
                "title": title,
                "content": text
            }

            file_name = os.path.join(output_dir, f"{len(visited)}.json")
            with open(file_name, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Find new links
            links = page.eval_on_selector_all("a[href]", "els => els.map(el => el.href)")
            for link in links:
                if link.startswith(base_url) and link not in visited:
                    to_visit.append(link)

            print(f"Crawled: {url}")

        browser.close()

    print(f"\nFinished. Saved {len(visited)} pages to '{output_dir}/'.")

# Example usage:
# crawl_js("https://www.leadifysolutions.xyz/", max_pages=30)


def parse_scraped_data():
    for file_name in os.listdir("scraped_data"):
        with open(os.path.join("scraped_data", file_name), "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"URL: {data['url']}")
            print(f"Title: {data['title']}")
            print(f"Content Snippet: {data['content'][:200]}...\n")
parse_scraped_data()