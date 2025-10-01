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
from app.utils.tools import replace_dynamic_variables
# from app.main import ResumeChat
# Load environment variables
load_dotenv()
api_key = os.getenv("OPEN_AI_API_KEY")
if not api_key:
    raise ValueError("OPEN_AI_API_KEY not found in .env file. Ensure .env contains: OPEN_AI_API_KEY=your-api-key-here")

# Initialize OpenAI client
client = OpenAI(base_url="https://openrouter.ai/api/v1",api_key=api_key)
# model = os.getenv("MODEL_NAME")
model="anthropic/claude-sonnet-4.5"
# Extract text from the PDF file
pdf_path = "Wallace Energy combined pdf.pdf"
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

company_name = "Wallace Energy"
company_specialization = "EV Charger installation"
company_documentation = pdf_text 
additional_info = """
Question: What if there aren’t enough EVs in my area yet?//nAnswer: EV adoption is growing rapidly, and installing chargers now positions your business ahead of the curve. Customers will view your location as forward-thinking and EV-friendly, which can attract new visitors before competitors catch up.//n//nQuestion: Isn't it too expensive to install?//nAnswer: While there is an upfront cost, there are federal, state, and utility incentives that can significantly reduce installation costs. Additionally, charging stations can generate revenue, increase foot traffic, and boost property value—turning the expense into an investment.//n//nQuestion: What if people don’t use it?//nAnswer: Most EV drivers plan their routes around charging availability. By providing a station, you not only meet a growing need but also attract drivers who will shop, dine, or spend time at your location while charging.//n//nQuestion: What about the hassle of managing it?//nAnswer: Many solutions include turnkey management—handling payments, software, and maintenance—so you can stay focused on your business while the charger operates smoothly.//n//nQuestion: What if I don't have the electrical capacity for it?//nAnswer: Part of our evaluation includes reviewing your existing electrical infrastructure. In many cases, upgrades are minor, and in others, phased solutions or load management systems can allow you to start with minimal changes.//n//nQuestion: How can I be sure it will provide a return on investment?//nAnswer: Beyond direct revenue from charging, stations increase dwell time, attract new customers, and enhance brand image. Properties with EV chargers also rent or sell faster at higher values.//n//nQuestion: Isn't maintenance a headache?//nAnswer: Modern charging stations are designed to be low-maintenance. We offer service agreements and monitoring so any issues can be quickly resolved, keeping downtime minimal.//n//nQuestion: What if technology changes and my station becomes outdated?//nAnswer: Charging technology is designed with scalability in mind. Many stations can be updated with new software or modular hardware upgrades, protecting your investment long-term.//n//nQuestion: What if I don't have room in my parking lot?//nAnswer: Chargers can be installed in just one or two existing parking spaces. They don’t require a lot of space, and signage can help designate them for EV use.//n//nQuestion: What if my customers don’t drive EVs?//nAnswer: Even if your current customers don’t, new ones will. Offering charging stations can attract a different demographic—EV drivers tend to have higher household incomes and actively seek out businesses with charging availability."""
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
        "description": "Add a new contact to GoHighLevel CRM with custom fields for booking status, date, and time. If the date and time are a string named cancelled, this is used to cancel the appointment booking. If new values for date and time are passed with the same name, email, and phone, then the booking date and time will be updated.",
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
                }, 
                "role": {
                    "type": "string",
                    "description": "Role of the contact in terms of decision maker."
                },
                "cause": {
                    "type": "string",
                    "description": "Cause of the reason for installation of the charger"
                },
                "address": {
                    "type": "string",
                    "description": "Address of the property where the charger is being installed."
                },
                "property_type": {
                    "type": "string",
                    "description": "Type of the property where the charger is being installed."
                },
                "property_details": {
                    "type": "string",
                    "description": "Details about the property where the charger is being installed"
                }
            },
            "required": ["name", "email", "phone", "booked", "date", "time", "role", "cause", "address", "property_type", "property_details"]
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
                        "Start date in UTC. Preferred format: 'YYYY-MM-DD HH:MM:SS'. "
                        "Also accepts ISO 8601 with Z suffix, e.g. '2025-09-05T00:00:00Z'. "
                        "If the user specifies 'today' or 'same day', "
                        "set this to 'YYYY-MM-DD 00:00:00'."
                    ),
                },
                "end_date": {
                    "type": "string",
                    "description": (
                        "End date in UTC. Preferred format: 'YYYY-MM-DD HH:MM:SS'. "
                        "Also accepts ISO 8601 with Z suffix, e.g. '2025-09-05T23:59:59Z'. "
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
MAX_EMPTY_RETRIES = 3  # safety cap to avoid infinite loops

def convert_messages_to_string(messages):
    """Convert session messages to a formatted string, preserving tool metadata."""
    conversation = ""
    try:
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '') if msg.get('content') is not None else ''
            conversation += f"Role: {role}\n"
            conversation += "Content:\n"
            conversation += content + "\n"
            if 'tool_calls' in msg:
                conversation += f"ToolCalls: {json.dumps(msg['tool_calls'])}\n"
            if 'tool_call_id' in msg:
                conversation += f"ToolCallID: {msg['tool_call_id']}\n"
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
            save_conversation(conversation, name, email, phone, booked, contact_id=contact_id, t=t, date=date)
        del sessions[sid]

    if session_id not in sessions:
        sessions[session_id] = {
            "messages": [
                {"role": "system", "content": instructions}
            ],
            "last_activity": current_time
        }

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
            save_conversation(conversation, name, email, phone, booked, contact_id=contact_id, t=t, date=date)

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
            content = {"message": "Chat session ended, no conversation found."}
            if name or email or phone or booked or contact_id or date or t:
                print("Saving ending session with contact details:", flush=True)
                print(f"Name: {name}, Email: {email}, Phone: {phone}, Booked: {booked}, Date: {date}, Time: {t}, Contact ID: {contact_id}", flush=True)
                save_conversation(conversation, name, email, phone, booked, contact_id=contact_id, t=t, date=date)
                content = {"message": "Chat session ended and saved."}
                if contact_id:
                    content["contact_id"] = contact_id
            del sessions[session_id]
            return JSONResponse(status_code=200, content=content)
        return JSONResponse(status_code=200, content={"message": "Chat session ended, no conversation found."})

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
            model=model, #"o1" gpt-4o-minni
            messages=sessions[session_id]["messages"],
            tools=[weather_tool, add_contact_tool, get_available_time_slots_tool, ],
            tool_choice="auto"
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Error calling chat completion: {str(e)}"})

    # Process the response
    choice = response.choices[0]
    is_new_contact = False
    extracted_contact_id = None
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
                    t=args["time"],
                    role=args.get("role", "N/A"),
                    cause=args.get("cause", "N/A"),
                    address=args.get("address", "N/A"),
                    property_type=args.get("property_type", "N/A"),
                    property_details=args.get("property_details", "N/A"),
                )
                print("Add contact result:", result, flush=True)
                tool_messages.append({
                    "role": "tool",
                    "content": json.dumps(result),
                    "tool_call_id": tool_call.id
                })
                try:
                    result_parsed = result if isinstance(result, dict) else json.loads(result)
                    contact = result_parsed.get("data", {}).get("contact", {})
                    extracted_contact_id = contact.get("id")
                    if extracted_contact_id:
                        is_new_contact = True
                except Exception as e:
                    print("Error extracting contact_id from add_contact result:", str(e), flush=True)
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
                model=model,
                messages=sessions[session_id]["messages"],
                tools=[weather_tool, add_contact_tool, get_available_time_slots_tool, ],
                tool_choice="auto"
            )
            response_message = final_response.choices[0].message.content
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f" in line 414{str(e)}"})

    else:
        response_message = choice.message.content

    # Retry loop to avoid returning empty responses
    attempts = 0
    while not response_message or not str(response_message).strip():
        if attempts >= MAX_EMPTY_RETRIES:
            response_message = "I’m here and ready to continue. Could you clarify what you’d like next?"
            break
        # Trace the empty response
        sessions[session_id]["messages"].append({
            "role": "assistant",
            "content": response_message or ""
        })
        # Add regeneration instruction
        sessions[session_id]["messages"].append({
            "role": "user",
            "content": "<admin>The previous response was empty, generate a response that continues the prior context naturally.</admin>"
        })
        try:
            fallback_response = client.chat.completions.create(
                model=model,
                messages=sessions[session_id]["messages"],
                tools=[weather_tool, add_contact_tool, get_available_time_slots_tool],
                tool_choice="auto"
            )
            fallback_choice = fallback_response.choices[0]
            if fallback_choice.finish_reason == "tool_calls":
                tool_calls_fb = fallback_choice.message.tool_calls
                sessions[session_id]["messages"].append({
                    "role": "assistant",
                    "content": fallback_choice.message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in tool_calls_fb
                    ]
                })
                tool_msgs_fb = []
                for tc in tool_calls_fb:
                    try:
                        if tc.type == "function" and tc.function.name == "get_weather":
                            args_fb = json.loads(tc.function.arguments)
                            tool_msgs_fb.append({"role": "tool", "content": get_weather(args_fb["city"]), "tool_call_id": tc.id})
                        elif tc.type == "function" and tc.function.name == "add_contact":
                            args_fb = json.loads(tc.function.arguments)
                            result_fb = add_contact(
                                name=args_fb["name"],
                                email=args_fb["email"],
                                phone=args_fb["phone"],
                                booked=args_fb["booked"],
                                date=args_fb["date"],
                                t=args_fb["time"],
                                role=args_fb.get("role", "N/A"),
                                cause=args_fb.get("cause", "N/A"),
                                address=args_fb.get("address", "N/A"),
                                property_type=args_fb.get("property_type", "N/A"),
                                property_details=args_fb.get("property_details", "N/A"),
                            )
                            tool_msgs_fb.append({"role": "tool", "content": json.dumps(result_fb), "tool_call_id": tc.id})
                        elif tc.type == "function" and tc.function.name == "get_available_time_slots":
                            args_fb = json.loads(tc.function.arguments)
                            result_fb = get_available_time_slots(args_fb["start_date"], args_fb["end_date"])
                            tool_msgs_fb.append({"role": "tool", "content": json.dumps(result_fb), "tool_call_id": tc.id})
                        elif tc.type == "function" and tc.function.name == "get_current_utc_datetime":
                            json.loads(tc.function.arguments)
                            now_fb = get_current_utc_datetime()
                            tool_msgs_fb.append({"role": "tool", "content": json.dumps(now_fb), "tool_call_id": tc.id})
                    except Exception as e:
                        tool_msgs_fb.append({"role": "tool", "content": json.dumps({"error": str(e)}), "tool_call_id": tc.id})
                sessions[session_id]["messages"].extend(tool_msgs_fb)
                # Finalize after tools
                try:
                    final_fb = client.chat.completions.create(
                        model=model,
                        messages=sessions[session_id]["messages"],
                        tools=[weather_tool, add_contact_tool, get_available_time_slots_tool],
                        tool_choice="auto"
                    )
                    response_message = final_fb.choices[0].message.content
                except Exception as e2:
                    response_message = f"<admin>Fallback tool phase failed: {str(e2)}</admin>"
            else:
                response_message = fallback_choice.message.content
        except Exception as e:
            response_message = f"<admin>Fallback attempt failed: {str(e)}</admin>"
            break
        attempts += 1

    # Append final assistant response (non-empty or final fallback)
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
            save_conversation(conversation, name, email, phone, booked, contact_id, t, date )

    content = {"message": response_message}
    if is_new_contact and extracted_contact_id:
        content["contact_id"] = extracted_contact_id
    return JSONResponse(status_code=200, content=content)

def resume_chat_session(contact_id: str, user_input: str, user, followup_stage: str = ""):
    """Resume or start a chat session from a conversation string, continue with new user input, and return updated conversation string.
   
    Args:
        contact_id: Unique identifier for the contact
        user_input: New user text prompt
        user: User details for dynamic variable replacement
        followup_stage: Optional stage for followup instructions
    """
    welcome_message = final_instructions
    if followup_stage:
        welcome_message = final_instructions
        messages = []
        conversation = get_conversation(contact_id)
        print("Retrieved conversation:", conversation, flush=True)

        # Parse conversation string into messages if provided
        if conversation:
            blocks = conversation.split("---\n")
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                lines = block.split("\n")
                msg = {}
                content_lines = []
                for line in lines:
                    if line.startswith("Role: "):
                        msg["role"] = line.replace("Role: ", "").strip()
                    elif line.startswith("Content:"):
                        # Start collecting content lines
                        pass
                    elif line.startswith("ToolCalls: "):
                        try:
                            msg["tool_calls"] = json.loads(line.replace("ToolCalls: ", "").strip())
                        except Exception:
                            pass
                    elif line.startswith("ToolCallID: "):
                        msg["tool_call_id"] = line.replace("ToolCallID: ", "").strip()
                    else:
                        content_lines.append(line)
                if msg.get("role") and (content_lines or msg.get("tool_calls")):
                    msg["content"] = "\n".join(content_lines).strip()
                    messages.append(msg)
        else:
            # Start new session with welcome message and stage 0 instructions
            messages.append({"role": "system", "content": welcome_message})
            instructions = os.getenv(f"FOLLOWUP_STAGE_0")
            if instructions:
                messages.append({"role": "system", "content": instructions})

        # Add followup stage instructions for non-zero stages
        if followup_stage:
            instruction_template = os.getenv(f"FOLLOWUP_STAGE_{followup_stage}")
            if instruction_template:
                print(user.name, user.email, user.phone, user.reply,flush=True)
                instructions = replace_dynamic_variables(instruction_template, user)
                print(f"instructions for followup stage {followup_stage}:", instructions, flush=True)
                messages.append({"role": "system", "content": instructions})
                # If no user_input, send the followup instructions to the LLM
                if not user_input:
                    if user.notes != None and followup_stage == "10":
                        messages.append({
                            "role": "user",
                            "content": "<admin>Generate the SMS follow-up message as per the instructions.</admin>"
                        })
                    try:
                        response = client.chat.completions.create(
                            model=model,
                            messages=messages,
                            tools=[weather_tool, add_contact_tool, get_available_time_slots_tool],
                            tool_choice="auto"
                        )
                        response_message = response.choices[0].message.content
                        messages.append({"role": "assistant", "content": response_message})
                        updated_conversation = convert_messages_to_string(messages)
                        save_conversation(conversation=updated_conversation, contact_id=contact_id)
                        print("TThis part is being executed line 572", flush=True)
                        print(response_message, flush=True)
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
                model=model,
                messages=messages,
                tools=[weather_tool, add_contact_tool, get_available_time_slots_tool],
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
                        return JSONResponse(status_code=500, content={"error": f"Error processing tool call: {str(e)}"})
                elif tool_call.type == "function" and tool_call.function.name == "add_contact":
                    args = json.loads(tool_call.function.arguments)
                    result = add_contact(
                        name=args["name"],
                        email=args["email"],
                        phone=args["phone"],
                        booked=args["booked"],
                        date=args["date"],
                        t=args["time"],
                        role=args.get("role", "N/A"),
                        cause=args.get("cause", "N/A"),
                        address=args.get("address", "N/A"),
                        property_type=args.get("property_type", "N/A"),
                        property_details=args.get("property_details", "N/A"),
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
                    model=model,
                    messages=messages,
                    tools=[weather_tool, add_contact_tool, get_available_time_slots_tool],
                    tool_choice="auto"
                )
                response_message = final_response.choices[0].message.content
            except Exception as e:
                return JSONResponse(status_code=500, content={"error": str(e)})
        else:
            response_message = choice.message.content

        # Retry loop to avoid empty responses
        attempts = 0
        while not response_message or not str(response_message).strip():
            if attempts >= MAX_EMPTY_RETRIES:
                response_message = "Just checking back in—let me know how you'd like to proceed."
                break
            messages.append({"role": "assistant", "content": response_message or ""})
            messages.append({
                "role": "user",
                "content": "<admin>The previous response was empty, generate a response that continues the context naturally.</admin>"
            })
            try:
                fb_resp = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=[weather_tool, add_contact_tool, get_available_time_slots_tool],
                    tool_choice="auto"
                )
                fb_choice = fb_resp.choices[0]
                if fb_choice.finish_reason == "tool_calls":
                    fb_tool_calls = fb_choice.message.tool_calls
                    messages.append({
                        "role": "assistant",
                        "content": fb_choice.message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            } for tc in fb_tool_calls
                        ]
                    })
                    fb_tool_msgs = []
                    for tc in fb_tool_calls:
                        try:
                            if tc.type == "function" and tc.function.name == "get_weather":
                                args_fb = json.loads(tc.function.arguments)
                                fb_tool_msgs.append({"role": "tool", "content": get_weather(args_fb["city"]), "tool_call_id": tc.id})
                            elif tc.type == "function" and tc.function.name == "add_contact":
                                args_fb = json.loads(tc.function.arguments)
                                result_fb = add_contact(
                                    name=args_fb["name"],
                                    email=args_fb["email"],
                                    phone=args_fb["phone"],
                                    booked=args_fb["booked"],
                                    date=args_fb["date"],
                                    t=args_fb["time"],
                                    role=args_fb.get("role", "N/A"),
                                    cause=args_fb.get("cause", "N/A"),
                                    address=args_fb.get("address", "N/A"),
                                    property_type=args_fb.get("property_type", "N/A"),
                                    property_details=args_fb.get("property_details", "N/A"),
                                )
                                fb_tool_msgs.append({"role": "tool", "content": json.dumps(result_fb), "tool_call_id": tc.id})
                            elif tc.type == "function" and tc.function.name == "get_available_time_slots":
                                args_fb = json.loads(tc.function.arguments)
                                result_fb = get_available_time_slots(args_fb["start_date"], args_fb["end_date"])
                                fb_tool_msgs.append({"role": "tool", "content": json.dumps(result_fb), "tool_call_id": tc.id})
                            elif tc.type == "function" and tc.function.name == "get_current_utc_datetime":
                                json.loads(tc.function.arguments)
                                now_fb = get_current_utc_datetime()
                                fb_tool_msgs.append({"role": "tool", "content": json.dumps(now_fb), "tool_call_id": tc.id})
                        except Exception as e:
                            fb_tool_msgs.append({"role": "tool", "content": json.dumps({"error": str(e)}), "tool_call_id": tc.id})
                    messages.extend(fb_tool_msgs)
                    try:
                        fb_final = client.chat.completions.create(
                            model=model,
                            messages=messages,
                            tools=[weather_tool, add_contact_tool, get_available_time_slots_tool],
                            tool_choice="auto"
                        )
                        response_message = fb_final.choices[0].message.content
                    except Exception as e2:
                        response_message = f"<admin>Fallback tool phase failed: {str(e2)}</admin>"
                else:
                    response_message = fb_choice.message.content
            except Exception as e:
                response_message = f"<admin>Fallback attempt failed: {str(e)}</admin>"
                break
            attempts += 1

        messages.append({
            "role": "assistant",
            "content": response_message
        })

        # Convert updated conversation to string
        updated_conversation = convert_messages_to_string(messages)
        save_conversation(conversation=updated_conversation, contact_id=contact_id)
        return JSONResponse(status_code=200, content={"message": response_message})

def add_ai_message(contact_id: str, ai_message: str):
    """Add an AI-generated message to the conversation history for a given contact ID.

    Args:
        contact_id: Unique identifier for the contact
        ai_message: The AI-generated message to append to the conversation
    """
    # Initialize messages list
    messages = []
    
    # Retrieve existing conversation
    conversation = get_conversation(contact_id)
    
    # Parse conversation string into messages if it exists
    if conversation:
        blocks = conversation.split("---\n")
        for block in blocks:
            if not block.strip():
                continue
            lines = block.split("\n")
            msg = {}
            content_lines = []
            collecting_content = False
            for line in lines:
                if line.startswith("Role: "):
                    msg["role"] = line.replace("Role: ", "").strip()
                    collecting_content = False
                elif line.startswith("Content:"):
                    collecting_content = True
                    continue
                elif line.startswith("ToolCalls: "):
                    msg["tool_calls"] = json.loads(line.replace("ToolCalls: ", "").strip())
                    collecting_content = False
                elif line.startswith("ToolCallID: "):
                    msg["tool_call_id"] = line.replace("ToolCallID: ", "").strip()
                    collecting_content = False
                elif collecting_content:
                    content_lines.append(line)
            if content_lines:
                msg["content"] = "\n".join(content_lines).strip()
            if msg.get("role"):
                messages.append(msg)
    
    # Append the new AI message
    messages.append({
        "role": "assistant",
        "content": ai_message + "<admin>This message was sent to the user via SMS</admin>"
    })
    
    # Convert updated conversation to string
    updated_conversation = convert_messages_to_string(messages)
    
    # Save the updated conversation
    try:
        save_conversation(conversation=updated_conversation, contact_id=contact_id)
        return JSONResponse(status_code=200, content={"status": "success", "message": "AI message added to conversation history"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})