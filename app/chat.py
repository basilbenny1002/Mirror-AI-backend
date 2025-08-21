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




# Load .env
load_dotenv()
api_key = os.getenv("OPEN_AI_API_KEY")

client = OpenAI(api_key=api_key)
chroma_client = chromadb.PersistentClient(path="chroma_store")  # stores DB in folder
collection = chroma_client.get_or_create_collection("CompanyData")



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
    with open("output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(texts))
    
    embeddings = []
    for t in texts:
        resp = client.embeddings.create(
            model="text-embedding-3-large",
            input=t
        )
        embeddings.append(resp.data[0].embedding) 
    for i, vec in enumerate(embeddings):
        collection.add(
            ids=[str(i)],             # <-- unique ID for each vector
            documents=[texts[i]], 
            embeddings=[vec]
        )

def query_company_details(query: str, top_k: int = 5):
    query_embedding = client.embeddings.create(
    model="text-embedding-3-large",
    input=query
    ).data[0].embedding

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3
    )
    print(results, flush=True)
    return f'The relevant data are:{results["documents"][0] if results["documents"] else "No relevant information found."}'


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
            },{
    "type": "function",
    "function": {
        "name": "query_company_details",
        "description": "Retrieve relevant details about a company from indexed documents. Useful for answering questions about a company's services, projects, or background.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The natural language question about the company. Example: 'name of the company', 'founded year', 'list of services', etc."
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of most relevant chunks to retrieve.",
                    "default": 5
                }
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
            print(f"Tool call: {fn_name} with args {tool_call.function.arguments}", flush=True)
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
            
            elif fn_name == "query_company_details":
                try:
                    result = query_company_details(args["query"], top_k=args.get("top_k", 5))
                except Exception as e:
                    result = f"Error querying company details: {str(e)}"
                    print(f"Error querying company details: {str(e)}", flush=True)
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
create_embeddings(pdf_path)
print("Embeddings created and stored in the vector database.")
# print(query_company_details("name of the company"))
