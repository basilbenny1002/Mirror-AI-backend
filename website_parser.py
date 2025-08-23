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
            summaries = summarize_data(data['content'])
            data = {"website": data['url'], "title": data['title'], "summaries": summaries}
            texts.append(data)

    embeddings = []
    limit = 0
    for page in texts:
        limit += 1
        if limit > 1:  
            break
        for t in page['summaries']:
            resp = client.embeddings.create(
                model="text-embedding-3-small",
                input=t
            )
            embeddings.append(resp.data[0].embedding) 
        for i, (summary, vec) in enumerate(zip(page['summaries'], embeddings)):
            collection.add(
                ids=[f"{page.get('url', '')}_{i}"],
                documents=[summary],
                embeddings=[vec],
                metadatas=[{
                    "url": page.get("url", ""),
                    "title": page.get("title", "")
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

# # parse_scraped_data()
# crawl_js("https://www.hubspot.com/", max_pages=6541)
# # print(query_website_data("pricing", top_k=3))

# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
# from reportlab.lib.styles import getSampleStyleSheet
# from reportlab.lib.pagesizes import A4

# # Text content from all the pages (from previous responses)
# homepage_text = """Leadify
# Home
# Features
# Pricing
# Contact
# Privacy Policy
# Refund Policy
# Sign In
# Sign Up
# Launching Soon: YouTube Scraper
# Find the Perfect Content Creators for Your Brand
# Leadify helps you discover, connect, and collaborate with content creators across multiple platforms.
# """

# features_text = """Features
# Discover Influencers: Access a database of content creators across platforms.
# Filter & Match: Find influencers based on category, reach, engagement, and more.
# Collaborate Easily: Connect directly and manage collaborations within the platform.
# Coming Soon: YouTube Scraper for advanced insights.
# """

# pricing_text = """Pricing
# Launching Soon!
# Our pricing plans will be available once the platform launches. Stay tuned for affordable and scalable options to fit your business needs.
# """

# privacy_policy_text = """Privacy Policy
# Effective Date: August 20, 2024
# Leadify (“we,” “our,” or “us”) values your privacy. This Privacy Policy explains how we collect, use, and protect your information.
# Information We Collect: Personal details such as name, email, business information.
# How We Use Information: To provide and improve our services, communicate with you, and ensure platform security.
# Data Protection: We implement measures to safeguard your data.
# Sharing Information: We do not sell your personal information. Data may be shared with trusted service providers under confidentiality agreements.
# Your Rights: You may request access, updates, or deletion of your personal data.
# Contact: For privacy concerns, please email us at support@leadifysolutions.xyz.
# """

# refund_policy_text = """Refund Policy
# Effective Date: August 20, 2024
# Thank you for choosing Leadify. If you are not satisfied with our service, this Refund Policy outlines your rights.
# Subscriptions: Subscriptions are generally non-refundable. However, exceptions may apply in cases of technical issues or service disruptions caused by us.
# Requesting a Refund: Email us at support@leadifysolutions.xyz within 7 days of your purchase to request a refund. Include your payment details and reason for the request.
# Eligibility: Refunds are evaluated on a case-by-case basis. Approved refunds will be processed within 7–10 business days to the original payment method.
# """

# contact_text = """Contact Us
# We’d love to hear from you!
# Email: support@leadifysolutions.xyz
# Stay connected for updates about Leadify and upcoming features.
# """

# # Combine all into one document
# doc = SimpleDocTemplate("LeadifySolutions_Info_FULL.pdf", pagesize=A4)
# styles = getSampleStyleSheet()
# story = []

# sections = [
#     ("Homepage", homepage_text),
#     ("Features", features_text),
#     ("Pricing", pricing_text),
#     ("Privacy Policy", privacy_policy_text),
#     ("Refund Policy", refund_policy_text),
#     ("Contact", contact_text)
# ]

# for title, content in sections:
#     story.append(Paragraph(f"<b>{title}</b>", styles['Heading2']))
#     story.append(Spacer(1, 8))
#     story.append(Paragraph(content.replace("\n", "<br/>"), styles['Normal']))
#     story.append(Spacer(1, 16))

# doc.build(story)
