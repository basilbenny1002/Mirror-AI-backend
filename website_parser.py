from playwright.sync_api import sync_playwright
import json, os
from openai import OpenAI
from dotenv import load_dotenv
import chromadb
load_dotenv()

client = OpenAI(api_key=os.getenv("OPEN_AI_API_KEY"))
chroma_client = chromadb.PersistentClient(path="chroma_store")  # stores DB in folder
collection = chroma_client.get_or_create_collection("WebsiteData")

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

def summarize_data(text: str): 
    prompt = f"""
    You are an assistant that extracts every detail from text.
    Convert the following text into clear, independent sentences.
    Each sentence must be standalone and not miss any detail.
    The output will be stored as vectors, so avoid combining points.
    Example format:
    - The company was founded in 2020.
    - The company name is ABC Corp.
    - The company provides services in web development and design.

    Text:
    {text}
    """

    response = client.chat.completions.create(
        model="gpt-4.1",  # largest context model
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    # Get model output
    output = response.choices[0].message.content.strip()

    # Split into list of sentences
    sentences = [s.strip("-• ").strip() for s in output.split("\n") if s.strip()]
    return sentences


def parse_scraped_data():
    texts = []
    for file_name in os.listdir("scraped_data"):
        with open(os.path.join("scraped_data", file_name), "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"URL: {data['url']}")
            print(f"Title: {data['title']}")
            print(f"Content Snippet: {data['content'][:200]}...\n")
            summaries = summarize_data(data['content'])
            data = {"website": data['url'], "title": data['title'], "summaries": summaries}
            texts.append(data)

    embeddings = []
    for page in texts:
        for t in page['summaries']:
            resp = client.embeddings.create(
                model="text-embedding-3-small",
                input=t
            )
            embeddings.append(resp.data[0].embedding) 
        for i, vec in enumerate(embeddings):
            collection.add(
                ids=[str(i)],             # <-- unique ID for each vector
                documents=[texts[i]], 
                embeddings=[vec],
                metadatas=[{
                "url": page["url"],
                "title": page["title"]
            }]
            )
        embeddings = []  

def query_website_data(query: str, top_k: int = 5):
    query_embedding = client.embeddings.create(
    model="text-embedding-3-small",
    input=query
    ).data[0].embedding

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    print(results, flush=True)
    if results["documents"]:
        snippets = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            snippets.append(f'"{doc}" (source: {meta["url"]})')
        return f'The relevant data are: {", ".join(snippets)}'
    else:
        return "No relevant information found."

