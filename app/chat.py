import os
import random
import json
import time
from dotenv import load_dotenv
from openai import OpenAI
from fastapi.responses import JSONResponse
import PyPDF2
from app.utils.tools import get_weather, add_contact, get_conversation, save_conversation, get_available_time_slots, get_current_utc_datetime
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
company_documentation = pdf_text 
additional_info = """
Leadify specializes in scraping Twitch to identify high-potential leads, such as streamers and content creators, and filtering them based on criteria like viewer count, engagement rates, content categories, or custom brand requirements. This enables brands to efficiently connect with a large number of creators for sponsorships, influencer partnerships, marketing campaigns, or community growth. For example, if a brand needs gaming influencers with 1,000+ average viewers for a campaign, Leadify’s process identifies, filters, and streamlines outreach to maximize ROI. Benefits include time savings, precise targeting, and scalable outreach, allowing brands to build impactful partnerships quickly.
"""
placeholders = {
    "_COMPANY_NAME_": company_name,
    "_COMPANY_SPECIALIZATION_": company_specialization,
    "_COMPANY_DOCUMENTATION_": company_documentation,
    "_ADDITIONAL_INFO_": additional_info
}
instructions_template_oneline = os.getenv("INSTRUCTIONS_TEMPLATE")

# Step 1: Replace the escaped newline characters (\\n) with actual newline characters (\n)
instructions_with_newlines = instructions_template_oneline.replace("\\n", "\n")

final_instructions = instructions_with_newlines
for placeholder, value in placeholders.items():
    if value is not None:
        final_instructions = final_instructions.replace(placeholder, value)


# instructions = final_instructions

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
        "description": "Add a new contact to GoHighLevel CRM with custom fields for booking status, date, and time.",
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
                    "description": "Phone number of the contact in E.164 format (+countrycode)."
                },
                "booked": {
                    "type": "string",
                    "description": "Booking status of the contact. Must be either 'yes' or 'no'."
                },
                "date": {
                    "type": "string",
                    "description": "Date of the booking in format DD-MMM-YYYY, e.g. '21-OCT-2021'."
                },
                "time": {
                    "type": "string",
                    "description": "Time of the booking in format HH:MM AM/PM, e.g. '08:30 AM'."
                }
            },
            "required": ["name", "email", "phone", "booked", "date", "time"]
        }
    }
}


get_available_time_slots_tool = {
    "type": "function",
    "function": {
        "name": "get_available_time_slots",
        "description": (
            "Fetch available meeting time slots from GoHighLevel in UTC timezone. "
            "The returned values contain dates with arrays of slots in ISO 8601 format "
            "(e.g., '2025-09-05T15:00:00Z'). "
            "The model should format these into user-friendly date and time "
            "when responding. Always mention that times are in UTC."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": (
                        "Start date in 'YYYY-MM-DD HH:MM:SS' format (UTC). "
                        "If the user specifies 'today' or 'same day', "
                        "set this to 'YYYY-MM-DD 00:00:00'."
                    ),
                },
                "end_date": {
                    "type": "string",
                    "description": (
                        "End date in 'YYYY-MM-DD HH:MM:SS' format (UTC). "
                        "If the user specifies 'today' or 'same day', "
                        "set this to 'YYYY-MM-DD 23:59:59'."
                    ),
                },
            },
            "required": ["start_date", "end_date"],
        },
    },
}





# Storage for sessions (session_id to conversation history)
sessions = {}


def convert_messages_to_string(messages):
    """Convert session messages to a formatted string."""
    conversation = ""
    try:
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '') if msg.get('content') is not None else ''
            conversation += f"Role: {role}\n"
            conversation += "Content:\n"
            conversation += content + "\n"
            conversation += "---\n"
    except Exception as e:
        print(f"Error converting messages to string: {str(e)}", flush=True)
        return conversation  # Return what was built so far
    return conversation

def chat_session(session_id: str, user_input: str, end: bool = False):
    """Manage a chat session with automatic cleanup after 1 hour of inactivity.
    
    Args:
        session_id: Unique identifier for the chat
        user_input: User text prompt
        end: If True, close the chat, call save_conversation with details, and clear session
    """
    # Check for inactive sessions (older than 1 hour)
    instructions = final_instructions.replace("_CURRENT_TIME_", get_current_utc_datetime())
    current_time = time.time()
    inactive_sessions = []
    for sid, session in sessions.items():
        if current_time - session.get("last_activity", current_time) > 3600:  # 1 hour in seconds
            inactive_sessions.append(sid)
    
    # Save and remove inactive sessions
    for sid in inactive_sessions:
        conversation = convert_messages_to_string(sessions[sid]["messages"])
        # Extract contact details from session if add_contact was called
        name, email, phone, booked, contact_id, date, t = None, None, None, None, None, None, None
        for i, msg in enumerate(sessions[sid]["messages"]):
            if msg["role"] == "tool" and "tool_call_id" in msg:
                # Look for the preceding assistant message with tool_calls
                if i > 0 and sessions[sid]["messages"][i-1]["role"] == "assistant" and "tool_calls" in sessions[sid]["messages"][i-1]:
                    for tool_call in sessions[sid]["messages"][i-1]["tool_calls"]:
                        if tool_call["function"]["name"] == "add_contact":
                            try:
                                result = json.loads(msg["content"])
                                print("Extracted add_contact result for inactive session:", result, flush=True)
                                contact = result.get("data", {}).get("contact", {})
                                name = contact.get("fullNameLowerCase")
                                email = contact.get("email")
                                phone = contact.get("phone")
                                booked = contact.get("customField", [{}])[0].get("fieldValue")
                                date = contact.get("customField", [{}])[1].get("fieldValue")
                                t = contact.get("customField", [{}])[2].get("fieldValue")
                                contact_id = contact.get("id")
                            except json.JSONDecodeError as e:
                                print("JSON decode error in inactive session add_contact parsing:", str(e), flush=True)
        if name or email or phone or booked or contact_id or date or t:
            print("Saving inactive session with contact details:", flush=True)
            print(f"Name: {name}, Email: {email}, Phone: {phone}, Booked: {booked}, Date: {date}, Time: {t}, Contact ID: {contact_id}", flush=True)
            save_conversation(conversation, name, email, phone, booked, date, t, contact_id)
        del sessions[sid]

    # Save conversation for current session if add_contact was called
    if session_id in sessions:
        conversation = convert_messages_to_string(sessions[session_id]["messages"])
        name, email, phone, booked, contact_id, date, t = None, None, None, None, None, None, None
        for i, msg in enumerate(sessions[session_id]["messages"]):
            if msg["role"] == "tool" and "tool_call_id" in msg:
                # Look for the preceding assistant message with tool_calls
                if i > 0 and sessions[session_id]["messages"][i-1]["role"] == "assistant" and "tool_calls" in sessions[session_id]["messages"][i-1]:
                    for tool_call in sessions[session_id]["messages"][i-1]["tool_calls"]:
                        if tool_call["function"]["name"] == "add_contact":
                            try:
                                result = json.loads(msg["content"])
                                print("Extracted add_contact result for current session:", result, flush=True)
                                contact = result.get("data", {}).get("contact", {})
                                name = contact.get("fullNameLowerCase")
                                email = contact.get("email")
                                phone = contact.get("phone")
                                booked = contact.get("customField", [{}])[0].get("fieldValue")
                                date = contact.get("customField", [{}])[1].get("fieldValue")
                                t = contact.get("customField", [{}])[2].get("fieldValue")
                                contact_id = contact.get("id")
                            except json.JSONDecodeError as e:
                                print("JSON decode error in current session add_contact parsing:", str(e), flush=True)
        if name or email or phone or booked or contact_id or date or t:
            print("Saving current session with contact details:", flush=True)
            print(f"Name: {name}, Email: {email}, Phone: {phone}, Booked: {booked}, Date: {date}, Time: {t}, Contact ID: {contact_id}", flush=True)
            save_conversation(conversation, name, email, phone, booked, date, t, contact_id)

    if end:
        if session_id in sessions:
            conversation = convert_messages_to_string(sessions[session_id]["messages"])
            # Extract contact details from session if add_contact was called
            name, email, phone, booked, contact_id, date, t = None, None, None, None, None, None, None
            for i, msg in enumerate(sessions[session_id]["messages"]):
                if msg["role"] == "tool" and "tool_call_id" in msg:
                    if i > 0 and sessions[session_id]["messages"][i-1]["role"] == "assistant" and "tool_calls" in sessions[session_id]["messages"][i-1]:
                        for tool_call in sessions[session_id]["messages"][i-1]["tool_calls"]:
                            if tool_call["function"]["name"] == "add_contact":
                                try:
                                    result = json.loads(msg["content"])
                                    print("Extracted add_contact result for ending session:", result, flush=True)
                                    contact = result.get("data", {}).get("contact", {})
                                    name = contact.get("fullNameLowerCase")
                                    email = contact.get("email")
                                    phone = contact.get("phone")
                                    booked = contact.get("customField", [{}])[0].get("fieldValue")
                                    date = contact.get("customField", [{}])[1].get("fieldValue")
                                    t = contact.get("customField", [{}])[2].get("fieldValue")
                                    contact_id = contact.get("id")
                                except json.JSONDecodeError as e:
                                    print("JSON decode error in ending session add_contact parsing:", str(e), flush=True)
            if name or email or phone or booked or contact_id or date or t:
                print("Saving ending session with contact details:", flush=True)
                print(f"Name: {name}, Email: {email}, Phone: {phone}, Booked: {booked}, Date: {date}, Time: {t}, Contact ID: {contact_id}", flush=True)
            save_conversation(conversation, name, email, phone, booked, date, t, contact_id)
            del sessions[session_id]
            return JSONResponse(status_code=200, content={"message": "Chat session ended and saved."})
        return JSONResponse(status_code=200, content={"message": "Chat session ended, no conversation found."})

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
            tools=[weather_tool, add_contact_tool, get_available_time_slots_tool, ],
            tool_choice="auto"
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Error calling chat completion: {str(e)}"})

    # Process the response
    choice = response.choices[0]
    if choice.finish_reason == "tool_calls":
        tool_calls = choice.message.tool_calls
        print("Tool calls received:", [tool_call.function.name for tool_call in tool_calls], flush=True)
        tool_messages = []
        # Append the assistant's message *with* tool_calls to the session history
        sessions[session_id]["messages"].append({
            "role": "assistant",
            "content": choice.message.content or "",
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                } for tool_call in tool_calls
            ]
        })

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
                    return JSONResponse(status_code=500, content={"error": f"Error processing tool call: {str(e)}"})
            elif tool_call.type == "function" and tool_call.function.name == "add_contact":
                args = json.loads(tool_call.function.arguments)
                print("Add contact called with args:", args, flush=True)
                result = add_contact(
                    name=args["name"],
                    email=args["email"],
                    phone=args["phone"],
                    booked=args["booked"],
                    date=args["date"],
                    t=args["time"]
                )
                print("Add contact result:", result, flush=True)
                tool_messages.append({
                    "role": "tool",
                    "content": json.dumps(result),
                    "tool_call_id": tool_call.id
                })
            elif tool_call.type == "function" and tool_call.function.name == "get_available_time_slots":
                try:
                    args = json.loads(tool_call.function.arguments)
                    print("Get available time slots called with args:", args, flush=True)
                    result = get_available_time_slots(args["start_date"], args["end_date"])
                    print("Get available time slots result:", result, flush=True)
                    tool_messages.append({
                        "role": "tool",
                        "content": json.dumps(result),
                        "tool_call_id": tool_call.id
                    })
                except Exception as e:
                    return JSONResponse(status_code=500, content={"error": f"Error processing tool call: {str(e)}"})
            elif tool_call.type == "function" and tool_call.function.name == "get_current_utc_datetime":
                try:
                    json.loads(tool_call.function.arguments)
                    print("Get current UTC datetime called", flush=True)
                    result = get_current_utc_datetime()
                    print("Get current UTC datetime result:", result, flush=True)
                    tool_messages.append({
                        "role": "tool",
                        "content": json.dumps(result),
                        "tool_call_id": tool_call.id
                    })
                except Exception as e:
                    return JSONResponse(status_code=500, content={"error": f"Error processing tool call: {str(e)}"})
        print("Tool messages to append:", tool_messages, flush=True)

        # Append tool messages to history
        sessions[session_id]["messages"].extend(tool_messages)

        # Submit tool outputs and get final response
        try:
            final_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=sessions[session_id]["messages"],
                tools=[weather_tool, add_contact_tool, get_available_time_slots_tool, ],
                tool_choice="auto"
            )
            response_message = final_response.choices[0].message.content
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f" in line 414{str(e)}"})

    else:
        response_message = choice.message.content

    # Append final assistant response to session history
    sessions[session_id]["messages"].append({
        "role": "assistant",
        "content": response_message
    })

    # Update last activity timestamp after successful response
    sessions[session_id]["last_activity"] = time.time()

    # Save conversation again after new message if add_contact was called
    if session_id in sessions:
        conversation = convert_messages_to_string(sessions[session_id]["messages"])
        name, email, phone, booked, contact_id, date, t = None, None, None, None, None, None, None
        for i, msg in enumerate(sessions[session_id]["messages"]):
            if msg["role"] == "tool" and "tool_call_id" in msg:
                if i > 0 and sessions[session_id]["messages"][i-1]["role"] == "assistant" and "tool_calls" in sessions[session_id]["messages"][i-1]:
                    for tool_call in sessions[session_id]["messages"][i-1]["tool_calls"]:
                        if tool_call["function"]["name"] == "add_contact":
                            try:
                                result = json.loads(msg["content"])
                                print("Extracted add_contact result for post-message save:", result, flush=True)
                                contact = result.get("data", {}).get("contact", {})
                                name = contact.get("fullNameLowerCase")
                                email = contact.get("email")
                                phone = contact.get("phone")
                                booked = contact.get("customField", [{}])[0].get("fieldValue")
                                date = contact.get("customField", [{}])[1].get("fieldValue")
                                t = contact.get("customField", [{}])[2].get("fieldValue")
                                contact_id = contact.get("id")
                            except json.JSONDecodeError as e:
                                print("JSON decode error in post-message add_contact parsing:", str(e), flush=True)
        if name or email or phone or booked or contact_id or date or t:
            print("Saving post-message session with contact details:", flush=True)
            print(f"Name: {name}, Email: {email}, Phone: {phone}, Booked: {booked}, Date: {date}, Time: {t}, Contact ID: {contact_id}", flush=True)
            save_conversation(conversation, name, email, phone, booked, date, t, contact_id)

    return JSONResponse(status_code=200, content={"message": response_message})


def resume_chat_session(contactID: str, user_input: str, followup_stage: str = ""):
    """Resume or start a chat session from a conversation string, continue with new user input, and return updated conversation string.
   
    Args:
        session_id: Unique identifier for the chat (not tied to global sessions)
        user_input: New user text prompt
        conversation: String containing the previous conversation (optional)
    """
    welcome_message = final_instructions
    if followup_stage:
        instructions = os.getenv(f"FOLLOWUP_STAGE_{followup_stage}")
        print(f"Followup stage {followup_stage} instructions: {instructions} ", flush=True)
    # Initialize local messages list
    messages = []
    conversation = get_conversation(contactID)
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
        # Start new session with welcome message and stage 0 instructions
        messages.append({"role": "system", "content": welcome_message})
        instructions = os.getenv(f"FOLLOWUP_STAGE_0")
        messages.append({"role": "system", "content": instructions})
       
        # For stage 0 (no conversation), process instructions and return response
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=[weather_tool, add_contact_tool, get_available_time_slots_tool, ],
                tool_choice="auto"
            )
            response_message = response.choices[0].message.content
            # Append assistant response to session history
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
            save_conversation(conversation=updated_conversation, contact_id=contactID)
            return JSONResponse(status_code=200, content={"message": response_message})
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})
    # Add followup stage instructions for non-zero stages
    if followup_stage:
        instructions = os.getenv(f"FOLLOWUP_STAGE_{followup_stage}")
        if instructions:
            messages.append({"role": "system", "content": instructions})
            # If no user_input, send the followup instructions to the LLM
            if not user_input:
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        tools=[weather_tool, add_contact_tool, get_available_time_slots_tool, ],
                        tool_choice="auto"
                    )
                    response_message = response.choices[0].message.content
                    # Append assistant response to session history
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
                    save_conversation(conversation=updated_conversation, contact_id=contactID)
                    return JSONResponse(status_code=200, content={"message": response_message})
                except Exception as e:
                    return JSONResponse(status_code=500, content={"error": str(e)})
    # Add new user message if provided
    if user_input:
        messages.append({
            "role": "user",
            "content": user_input
        })
    # Prepare the API request
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=[weather_tool, add_contact_tool, get_available_time_slots_tool, ],
            tool_choice="auto"
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    # Process the response
    choice = response.choices[0]
    if choice.finish_reason == "tool_calls":
        tool_calls = choice.message.tool_calls
        tool_messages = []
       
        # Append the assistant's message *with* tool_calls to the history
        messages.append({
            "role": "assistant",
            "content": choice.message.content or "",
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                } for tool_call in tool_calls
            ]
        })
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
                    return JSONResponse(status_code=500, content={"message": f"Error processing tool call: {str(e)}", "conversation": conversation})
            elif tool_call.type == "function" and tool_call.function.name == "add_contact":
                args = json.loads(tool_call.function.arguments)
                result = add_contact(
                    name=args["name"],
                    email=args["email"],
                    phone=args["phone"],
                    booked=args["booked"],
                    date=args["date"],
                    t=args["time"]
                )
                tool_messages.append({
                    "role": "tool",
                    "content": json.dumps(result),
                    "tool_call_id": tool_call.id
                })
            elif tool_call.type == "function" and tool_call.function.name == "get_available_time_slots":
                try:
                    args = json.loads(tool_call.function.arguments)
                    print("Get available time slots called with args:", args, flush=True)
                    result = get_available_time_slots(args["start_date"], args["end_date"])
                    print("Get available time slots result:", result, flush=True)
                    tool_messages.append({
                        "role": "tool",
                        "content": json.dumps(result),
                        "tool_call_id": tool_call.id
                    })
                except Exception as e:
                    return JSONResponse(status_code=500, content={"error": f"Error processing tool call: {str(e)}"})
            elif tool_call.type == "function" and tool_call.function.name == "get_current_utc_datetime":
                try:
                    json.loads(tool_call.function.arguments)
                    print("Get current UTC datetime called", flush=True)
                    result = get_current_utc_datetime()
                    print("Get current UTC datetime result:", result, flush=True)
                    tool_messages.append({
                        "role": "tool",
                        "content": json.dumps(result),
                        "tool_call_id": tool_call.id
                    })
                except Exception as e:
                    return JSONResponse(status_code=500, content={"error": f"Error processing tool call: {str(e)}"})
        # Append tool response messages to history
        messages.extend(tool_messages)
        # Submit tool outputs and get final response
        try:
            final_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=[weather_tool, add_contact_tool, get_available_time_slots_tool, ],
                tool_choice="auto"
            )
            response_message = final_response.choices[0].message.content
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})
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
    save_conversation(conversation=updated_conversation, contact_id=contactID)
    return JSONResponse(status_code=200, content={"message": response_message})