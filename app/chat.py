import os
import random
import json
import time
from dotenv import load_dotenv
from openai import OpenAI
from fastapi.responses import JSONResponse
import PyPDF2
from app.utils.tools import get_weather, add_contact
from pathlib import Path
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

company_name = "Leadify"
company_specialization = "lead generation"
company_documentation = pdf_text  # Assuming 'pdf_text' is the variable from your original code containing the extracted PDF text
additional_info = """
Leadify specializes in scraping Twitch to identify high-potential leads, such as streamers and content creators, and filtering them based on criteria like viewer count, engagement rates, content categories, or custom brand requirements. This enables brands to efficiently connect with a large number of creators for sponsorships, influencer partnerships, marketing campaigns, or community growth. For example, if a brand needs gaming influencers with 1,000+ average viewers for a campaign, Leadify’s process identifies, filters, and streamlines outreach to maximize ROI. Benefits include time savings, precise targeting, and scalable outreach, allowing brands to build impactful partnerships quickly.
"""

# The full dynamic system prompt as a multi-line string, formatted with the variables

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
add_contact_tool = {
    "type": "function",
    "function": {
        "name": "add_contact",
        "description": "Add a new contact to GoHighLevel CRM with custom fields for booking status and conversation notes.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Full name of the contact (first and last name)."
                },
                "email": {
                    "type": "string",
                    "description": "Email address of the contact."
                },
                "phone": {
                    "type": "string",
                    "description": "Phone number of the contact in E.164 format (+countrycodexxxxxxxxxx)."
                },
                "booked": {
                    "type": "string",
                    "description": "Booking status or details about the booked call/meeting."
                },
                "conversation": {
                    "type": "string",
                    "description": "Conversation notes or details about prior interactions with the contact."
                }
            },
            "required": ["name", "email", "phone", "booked", "conversation"]
        }
    }
}


# Storage for sessions (session_id to conversation history)
sessions = {}



def chat_session(session_id: str, user_input: str, end: bool = False):
    """Manage a chat session with automatic cleanup after 1 hour of inactivity.
    
    Args:
        session_id: Unique identifier for the chat
        user_input: User text prompt
        end: If True, close the chat, call save_conversation with details, and clear session
    """
    # Check for inactive sessions (older than 1 hour)
    current_time = time.time()
    inactive_sessions = []
    for sid, session in sessions.items():
        if current_time - session.get("last_activity", current_time) > 3600:  # 1 hour in seconds
            inactive_sessions.append(sid)
    
    # Save and remove inactive sessions
    for sid in inactive_sessions:
        conversation = ""
        for msg in sessions[sid]["messages"]:
            conversation += f"Role: {msg['role']}\n"
            conversation += "Content:\n"
            conversation += msg['content'] + "\n"
            conversation += "---\n"
        # Extract contact details from session if add_contact was called
        name, email, phone, booked = None, None, None, None
        for msg in sessions[sid]["messages"]:
            if msg["role"] == "tool" and "add_contact" in msg.get("content", ""):
                try:
                    result = json.loads(msg["content"])
                    name = result.get("name")
                    email = result.get("email")
                    phone = result.get("phone")
                    booked = result.get("booked")
                except json.JSONDecodeError:
                    pass
        save_conversation(sid, conversation, name, email, phone, booked)
        del sessions[sid]

    if end:
        if session_id in sessions:
            # Convert conversation to plain text string
            conversation = ""
            for msg in sessions[session_id]["messages"]:
                conversation += f"Role: {msg['role']}\n"
                conversation += "Content:\n"
                conversation += msg['content'] + "\n"
                conversation += "---\n"
            # Extract contact details from session if add_contact was called
            name, email, phone, booked = None, None, None, None
            for msg in sessions[session_id]["messages"]:
                if msg["role"] == "tool" and "add_contact" in msg.get("content", ""):
                    try:
                        result = json.loads(msg["content"])
                        name = result.get("name")
                        email = result.get("email")
                        phone = result.get("phone")
                        booked = result.get("booked")
                    except json.JSONDecodeError:
                        pass
            save_conversation(session_id, conversation, name, email, phone, booked)
            del sessions[session_id]
            return {"message": "Chat session ended and saved."}
        return {"message": "Chat session ended, no conversation found."}

    if session_id not in sessions:
        sessions[session_id] = {
            "messages": [
                {"role": "system", "content": instructions}
            ],
            "last_activity": current_time
        }

    # Update last activity timestamp
    sessions[session_id]["last_activity"] = current_time

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
            tools=[weather_tool, add_contact_tool],
            tool_choice="auto"
        )
    except Exception as e:
        return {"error": f"Error calling chat completion: {str(e)}"}

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
                    return {"error": f"Error processing tool call: {str(e)}"}
            elif tool_call.type == "function" and tool_call.function.name == "add_contact":
                args = json.loads(tool_call.function.arguments)
                result = add_contact(
                    name=args["name"],
                    email=args["email"],
                    phone=args["phone"],
                    booked=args["booked"]
                )
                tool_messages.append({
                    "role": "tool",
                    "content": json.dumps(result),
                    "tool_call_id": tool_call.id
                })

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
            return {"error": f"Error submitting tool outputs: {str(e)}"}
    else:
        response_message = choice.message.content

    # Append final assistant response to session history
    sessions[session_id]["messages"].append({
        "role": "assistant",
        "content": response_message
    })

    # Update last activity timestamp after successful response
    sessions[session_id]["last_activity"] = time.time()

    return {"message": response_message}



def resume_chat_session(session_id: str, user_input: str, conversation: str = ""):
    """Resume or start a chat session from a conversation string, continue with new user input, and return updated conversation string.
    
    Args:
        session_id: Unique identifier for the chat (not tied to global sessions)
        user_input: New user text prompt
        conversation: String containing the previous conversation (optional)
    """
    # Initialize local messages list
    messages = []

    # Parse conversation string into messages if provided
    if conversation:
        blocks = conversation.split("---\n")
        for block in blocks:
            if not block.strip():
                continue
            lines = block.split("\n")
            role = lines[0].replace("Role: ", "").strip()
            content_start = lines[1].replace("Content: ", "").strip()
            messages.append({"role": role, "content": content_start})
    else:
        # Start new session with system instructions
        messages.append({"role": "system", "content": instructions})

    # Add new user message
    messages.append({
        "role": "user",
        "content": user_input
    })

    # Prepare the API request
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=[weather_tool, add_contact_tool],
            tool_choice="auto"
        )
    except Exception as e:
        return {"message": f"Error calling chat completion: {str(e)}", "conversation": conversation}

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
                    return {"message": f"Error processing tool call: {str(e)}", "conversation": conversation}
            elif tool_call.type == "function" and tool_call.function.name == "add_contact":
                args = json.loads(tool_call.function.arguments)
                result = add_contact(
                    name=args["name"],
                    email=args["email"],
                    phone=args["phone"],
                    booked=args["booked"],
                    conversation=args["conversation"]
                )
                tool_messages.append({
                    "role": "tool",
                    "content": json.dumps(result),
                    "tool_call_id": tool_call.id
                })

        # Append assistant message (without tool_calls) to history
        messages.append({
            "role": "assistant",
            "content": choice.message.content or ""
        })

        # Append tool response messages to history
        messages.extend(tool_messages)

        # Submit tool outputs and get final response
        try:
            final_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=[weather_tool],
                tool_choice="auto"
            )
            response_message = final_response.choices[0].message.content
        except Exception as e:
            return {"message": f"Error submitting tool outputs: {str(e)}", "conversation": conversation}
    else:
        response_message = choice.message.content

    # Append final assistant response to session history
    messages.append({
        "role": "assistant",
        "content": response_message
    })

    # Convert updated conversation to string
    updated_conversation = ""
    for msg in messages:
        updated_conversation += f"Role: {msg['role']}\n"
        updated_conversation += f"Content: {msg['content']}\n"
        updated_conversation += "---\n"

    return {"message": response_message, "conversation": updated_conversation}