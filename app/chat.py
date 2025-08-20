import os
import random
import json
from dotenv import load_dotenv
from openai import OpenAI

# Load .env
load_dotenv()
api_key = os.getenv("OPEN_AI_API_KEY")

client = OpenAI(api_key=api_key)


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
                return final_msg
    else:
        ai_response = msg.content
        messages.append({"role": "assistant", "content": ai_response})
        return ai_response
