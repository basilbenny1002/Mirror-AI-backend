import os
import random
import json
import time
from dotenv import load_dotenv
from openai import OpenAI
from fastapi.responses import JSONResponse
import PyPDF2

# Load environment variables
load_dotenv()
api_key = os.getenv("OPEN_AI_API_KEY")
if not api_key:
    raise ValueError("OPEN_AI_API_KEY not found in .env file. Ensure .env contains: OPEN_AI_API_KEY=your-api-key-here")

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

# Extract text from the PDF file
pdf_path = "LeadifySolutions_Info_FULL.pdf"
if not os.path.exists(pdf_path):
    raise FileNotFoundError(f"PDF file not found at {pdf_path}")

try:
    with open(pdf_path, "rb") as file:
        pdf_reader = PyPDF2.PdfReader(file)
        pdf_text = ""
        for page in pdf_reader.pages:
            extracted_text = page.extract_text()
            if extracted_text:
                pdf_text += extracted_text + "\n"
        if not pdf_text:
            raise ValueError("No text could be extracted from the PDF.")
except Exception as e:
    raise Exception(f"Failed to process PDF: {str(e)}")

# System instructions
instructions = f"""You are a helpful assistant. Use the following information from the PDF to answer user questions. info {pdf_text}"""

# Define the get_weather tool
weather_tool = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get weather for a given city",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name"
                }
            },
            "required": ["city"]
        }
    }
}

# Storage for sessions (session_id to conversation history)
sessions = {}

def get_weather(city: str):
    """Generate random weather conditions for a given city."""
    temp = random.randint(10, 40)
    conditions = random.choice(["sunny", "cloudy", "rainy", "windy"])
    return f"The weather in {city} is {temp}°C and {conditions}."

def chat_session(session_id: str, user_input: str, end: bool = False):
    """Manage a chat session.
    
    Args:
        session_id: Unique identifier for the chat
        user_input: User text prompt
        end: If True, close the chat and return final response
    """
    if end:
        if session_id in sessions:
            del sessions[session_id]
        return "Chat session ended."

    if session_id not in sessions:
        sessions[session_id] = {
            "messages": [
                {"role": "system", "content": instructions}
            ]
        }

    # Add user message to session history
    sessions[session_id]["messages"].append({
        "role": "user",
        "content": user_input
    })

    # Prepare the API request
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=sessions[session_id]["messages"],
            tools=[weather_tool],
            tool_choice="auto"
        )
    except Exception as e:
        return f"Error calling chat completion: {str(e)}"

    # Process the response
    choice = response.choices[0]
    if choice.finish_reason == "tool_calls":
        tool_calls = choice.message.tool_calls
        tool_messages = []
        for tool_call in tool_calls:
            if tool_call.type == "function" and tool_call.function.name == "get_weather":
                try:
                    args = json.loads(tool_call.function.arguments)
                    result = get_weather(args["city"])
                    tool_messages.append({
                        "role": "tool",
                        "content": result,
                        "tool_call_id": tool_call.id
                    })
                except Exception as e:
                    return JSONResponse( status_code=500, content={"message":f"Error processing tool call: {str(e)}"})

        # Append assistant message (without tool_calls) to history
        sessions[session_id]["messages"].append({
            "role": "assistant",
            "content": choice.message.content or ""
        })

        # Append tool response messages to history
        sessions[session_id]["messages"].extend(tool_messages)

        # Submit tool outputs and get final response
        try:
            final_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=sessions[session_id]["messages"],
                tools=[weather_tool],
                tool_choice="auto"
            )
            response_message = final_response.choices[0].message.content
        except Exception as e:
            return JSONResponse( status_code=500, content={"message":f"Error submitting tool outputs: {str(e)}"})
    else:
        response_message = choice.message.content

    # Append final assistant response to session history
    sessions[session_id]["messages"].append({
        "role": "assistant",
        "content": response_message
    })

    return JSONResponse( status_code=200, content={"message":response_message})

