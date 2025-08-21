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
import faiss
from dotenv import load_dotenv
from openai import OpenAI
from PyPDF2 import PdfReader
from fastapi.responses import JSONResponse

# Load .env
load_dotenv()
api_key = os.getenv("OPEN_AI_API_KEY")

client = OpenAI(api_key=api_key)



def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def chunk_text(text, chunk_size=500):
    words = text.split()
    chunks, current = [], []
    for word in words:
        current.append(word)
        if len(current) >= chunk_size:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks

def build_faiss_index(pdf_path):
    text = extract_text_from_pdf(pdf_path)
    chunks = chunk_text(text)

    embeddings = [
        client.embeddings.create(model="text-embedding-3-small", input=chunk).data[0].embedding
        for chunk in chunks
    ]

    dim = len(embeddings[0])
    index = faiss.IndexFlatL2(dim)
    index.add(np.array(embeddings).astype("float32"))

    return index, chunks

def search_docs(query, index, chunks, top_k=3):
    q_emb = client.embeddings.create(model="text-embedding-3-small", input=query).data[0].embedding
    D, I = index.search(np.array([q_emb]).astype("float32"), top_k)
    return [chunks[i] for i in I[0]]

def company_docs(query: str):
    results = search_docs(query, doc_index, doc_chunks)
    return "\n".join(results)

# Fake weather tool
def get_weather(city: str):
    temp = random.randint(10, 40)
    conditions = random.choice(["sunny", "cloudy", "rainy", "windy"])
    return f"The weather in {city} is {temp}°C and {conditions}."


# Storage for chat sessions
chats = {}


def chat_session(session_id: str, user_input: str, end: bool = False):
    """
    Manage a chat session.
    session_id: unique identifier for the chat
    user_input: user text prompt
    end: if True, close the chat and return final response
    """
    # End chat
    if end:
        if session_id in chats:
            del chats[session_id]
        return "Chat session ended."

    # Create new session if not exist
    if session_id not in chats:
        chats[session_id] = [
            {"role": "system", "content": "You are a helpful assistant. If you need weather info, call the tool 'get_weather'."}
        ]

    messages = chats[session_id]

    # Add user message
    messages.append({"role": "user", "content": user_input})

    # Send to model
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather for a given city",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "City name"}
                        },
                        "required": ["city"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "company_docs",
                    "description": "Search company PDF knowledge base",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"]
                    }
                }
            }
        ]
    )

    msg = response.choices[0].message

    # Handle tool call
    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            if fn_name == "get_weather":
                result = get_weather(args["city"])
                messages.append({"role": "assistant", "content": None, "tool_calls": msg.tool_calls})
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})

                followup = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages
                )
                final_msg = followup.choices[0].message.content
                messages.append({"role": "assistant", "content": final_msg})
                return JSONResponse(status_code=200,content={"message": final_msg, "session_id": session_id})
    else:
        ai_response = msg.content
        messages.append({"role": "assistant", "content": ai_response})
        return JSONResponse(status_code=200,content={"message": ai_response, "session_id": session_id})


pdf_path = "company_info.pdf"   
doc_index, doc_chunks = build_faiss_index(pdf_path)

print(chat_session("HEHEEHEHE", "hey, what's up?"))