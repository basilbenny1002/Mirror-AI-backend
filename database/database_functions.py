import os
import random
import json
from dotenv import load_dotenv
from openai import OpenAI
from fastapi.responses import JSONResponse
import os
import random
import json
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from PyPDF2 import PdfReader
from fastapi.responses import JSONResponse
import sys
from chromadb.utils import embedding_functions
from chromadb import Client
import io
import nltk
import chromadb

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
load_dotenv()
api_key = os.getenv("OPEN_AI_API_KEY")
system_prompt = os.getenv("SYSTEM_PROMPT", "You are a helpful assistant.")

client = OpenAI(api_key=api_key)
# chroma_client = chromadb.PersistentClient(path="chroma_store")  # stores DB in folder
# collection = chroma_client.get_or_create_collection("CompanyData")

chroma_client = chromadb.PersistentClient(path="test_store")  # stores DB in folder
collection = chroma_client.get_or_create_collection("LeadifyData")


def create_embeddings(file_path: str):
    """
    Create an embedding function using OpenAI's API.
    """
    reader = PdfReader(file_path)
    texts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            texts.extend(text.split("."))
    # with open("output.txt", "w", encoding="utf-8") as f:
    #     f.write("\n".join(texts))
    
    embeddings = []
    for t in texts:
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=t
        )
        embeddings.append(resp.data[0].embedding) 
    for i, vec in enumerate(embeddings):
        collection.add(
            ids=[str(i)],             # <-- unique ID for each vector
            documents=[texts[i]], 
            embeddings=[vec]
        )


def query_website_data(query: str, top_k: int = 3):
    query_embedding = client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    ).data[0].embedding

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    matches = results["documents"]
    print(f"Query: {query}", flush=True)

    return str(matches) if matches else ["No relevant information found."]

# def query_company_details(query: str, top_k: int = 5):
#     query_embedding = client.embeddings.create(
#     model="text-embedding-3-small",
#     input=query
#     ).data[0].embedding

#     results = collection.query(
#         query_embeddings=[query_embedding],
#         n_results=top_k
#     )
#     print(results, flush=True)
#     return f'The relevant data are:{results["documents"][0] if results["documents"] else "No relevant information found."}'
