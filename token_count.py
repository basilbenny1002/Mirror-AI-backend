# import os
# import json
# import tiktoken

# # Choose model tokenizer (use gpt-4o-mini, gpt-3.5-turbo, etc.)
# encoding = tiktoken.encoding_for_model("gpt-4o-mini")

# def count_tokens(text: str) -> int:
#     """Count tokens in a string using tiktoken."""
#     return len(encoding.encode(text))

# folder_path = "scraped_data"  # adjust if needed
# total_tokens = 0
# file_token_counts = {}

# for file_name in os.listdir(folder_path):
#     if file_name.endswith(".json"):
#         file_path = os.path.join(folder_path, file_name)
#         with open(file_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
        
#         # combine title + content (you can tweak this)
#         text = f"{data.get('title', '')}\n{data.get('content', '')}"
#         tokens = count_tokens(text)
#         file_token_counts[file_name] = tokens
#         total_tokens += tokens

# # Print results
# print("Token counts per file:")
# for file, tokens in file_token_counts.items():
#     print(f"{file}: {tokens}")

# print(f"\nTotal tokens across all files: {total_tokens}")


# # import os
# # from dotenv import load_dotenv
# # from openai import OpenAI

# # load_dotenv()
# # client = OpenAI(api_key=os.getenv("OPEN_AI_API_KEY"))

# # history = []

# # def ask(question: str):
# #     history.append({"role": "user", "content": question})
# #     response = client.responses.create(
# #         model="gpt-5",
# #         tools=[{"type": "web_search_preview"}],
# #         input=question
# #     )
# #     answer = response.output_text
# #     history.append({"role": "assistant", "content": answer})
# #     return answer

# # if __name__ == "__main__":
# #     print("Assistant ready (using web search tool) — type 'exit' to quit.")
# #     while True:
# #         user_input = input("You: ")
# #         if user_input.strip().lower() in {"exit", "quit"}:
# #             break
# #         reply = ask(user_input)
# #         print("Assistant:", reply, "\n")



from openai import OpenAI
import textwrap
import os
import chromadb
from dotenv import load_dotenv
load_dotenv()
client = OpenAI(api_key=os.getenv("OPEN_AI_API_KEY"))

# -----------------------------
# 1. Prepare Refund Policy Text
# -----------------------------
refund_policy_text = """
Leadify Solutions — Home Page

Launching Soon: YouTube Scraper

Find the Perfect Content Creators for Your Brand

Leadify helps you discover, connect with, and manage relationships with the right content creators to amplify your brand's message.

Get Started Free — No credit card required

See How It Works

Free plan available

Trusted by marketing teams at:
ThreeCloverMedia, Organix, Nexus Ai, Fulfilledge

Why Choose Leadify?

Data-Driven Decisions
Make informed choices using comprehensive analytics and insights, including engagement rates, audience demographics, and performance trends.

Time-Saving Automation
Automate repetitive tasks—data collection, filtering, outreach—so you can focus on building meaningful creator relationships.

Global Reach
Connect with content creators worldwide; discover creators in multiple languages and regions to expand your brand’s global presence.

Team Collaboration
Share saved searches, notes, and outreach history with your team to stay aligned and work efficiently.

Compliance & Privacy
Designed with privacy in mind; ensures that all data collection and processing complies with relevant regulations.

Seamless Integrations
Integrate with popular CRM systems, email marketing platforms, and spreadsheet applications to fit into your existing workflow.

Powerful Tools for Influencer Discovery

Advanced Search & Filtering
Find creators by language, follower/viewer count, content type, and more.

Comprehensive Analytics
Access detailed metrics and insights to support data-driven decisions.

Contact Information Access
Retrieve public contact details and social media profiles to streamline outreach.

Data Export & Integration
Export data in multiple formats for easy integration with your tools and workflows.

Twitch Scraper — (mention suggests specialized Twitch data scraping functionality)

What Our Customers Say

JD, Marketing Director, TechCorp

"Leadify has transformed our influencer marketing strategy. We've been able to find creators who truly align with our brand values, resulting in more authentic partnerships and higher ROI."

MS, Growth Lead, StartupX

"The time we save using Leadify is incredible. What used to take days of manual research now takes minutes. The advanced filtering options help us pinpoint exactly the type of creators we need."

Call to Action

Ready to Transform Your Influencer Marketing?
Choose the plan that works best for your business needs. All plans include access to our core features.

Get Started Free

View Pricing

14-day free trial — No credit card required

Cancel anytime

Footer

Navigation Links: Home | Features | Pricing | Contact | Privacy Policy | Refund Policy

© 2025 Leadify, Inc. All rights reserved.

"""

# -----------------------------
# 2. Function to Store in DB
# -----------------------------
def store_policy_in_db(text: str, collection):
    # break text into chunks (per paragraph/line)
    chunks = [chunk.strip() for chunk in textwrap.dedent(text).split("\n\n") if chunk.strip()]

    for i, chunk in enumerate(chunks):
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=chunk
        )
        embedding = resp.data[0].embedding

        collection.add(
            ids=[f"refund_policy_{i}"],
            documents=[chunk],
            embeddings=[embedding]
        )
    print(f"Stored {len(chunks)} refund policy chunks into vector DB.")


# -----------------------------
# 3. Query Function
# -----------------------------
def query_refund_policy(query: str, collection, top_k: int = 3):
    query_embedding = client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    ).data[0].embedding

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    matches = results["documents"]

    return matches if matches else ["No relevant information found."]



chroma_client = chromadb.PersistentClient(path="test_store")  # stores DB in folder
collection = chroma_client.get_or_create_collection("LeadifyData")

store_policy_in_db(refund_policy_text, collection)

# 2. Query
print(query_refund_policy("Can I get a cash refund if I cancel my subscription?", collection))
print(query_refund_policy("What happens if I report an issue within 30 days?", collection))