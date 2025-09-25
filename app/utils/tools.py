import random
# from database.insights_db import save_insight, search_insight
from zoneinfo import ZoneInfo
import os
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime
import http.client
import json
from datetime import datetime, timezone, timedelta
import requests


# Load environment variables
load_dotenv()
API_KEY = os.getenv("GHL_API_KEY")

# Mongo setup (put your URI in .env as MONGO_URI)
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["ghl_contacts"]
conversations_col = db["conversations"]


if not API_KEY:
    raise ValueError("GHL_API_KEY not found in .env file")

# Endpoint + headers
GHL_URL = "https://rest.gohighlevel.com/v1/contacts/"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Replace these with your actual custom field IDs
BOOKED_FIELD_ID = "59g21lZwv0U3YJBXtQcc"#"r9wLa2H8weqkXfIHgmLA" 59g21lZwv0U3YJBXtQcc       # e.g. "Booked Call" field
TIME_FIELD_ID = "B4x2SRqU3csMnTw6q8mo"#"Ogr5kUZzwCTtMXQxMf17"   B4x2SRqU3csMnTw6q8mo       # e.g. "Call Time" field
DATE_FIELD_ID = "4V5u1RjpZ5Lna5QNLeZr"#"SMDVlM8yUR534vvOPkjn"    "4V5u1RjpZ5Lna5QNLeZr"      # e.g. "Call Date" field
ROLE_FIELD_ID = "DUHytN2BwNIfmriWngqJ"  # e.g. "Role" field
CAUSE_FIELD_ID = "J1bOi2Ab8Uft3Ikrbfqg"  # e.g. "Cause" field
ADDRESS_FIELD_ID = "iuisj6SiXN5nGWWXwqHJ"  # e.g. "Address" field
PROPERTY_TYPE_FIELD_ID = "Zga17He1MM0vIc9WgVcx"  # e.g. "Property" field
PROPERTY_DETAILS_FIELD_ID = "X0BJ4sYFkBZmD4z3L0lm"  # e.g. "Property Details" field

def to_unix(date_str: str) -> int:
    if not date_str:
        return ""
    """
    Convert a string in 'YYYY-MM-DD HH:MM:SS' format (UTC) to Unix timestamp (seconds).
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    # Treat it as UTC
    return int(dt.replace(tzinfo=timezone.utc).timestamp()) * 1000

# def to_unix(date_str: str) -> int:
#     """
#     Convert a UTC date string to a Unix timestamp in milliseconds.
#     Accepts:
#       - 'YYYY-MM-DD HH:MM:SS'
#       - 'YYYY-MM-DDTHH:MM:SSZ'
#     """
#     if not date_str:
#         return ""

#     try:
#         # Case 1: "YYYY-MM-DD HH:MM:SS"
#         dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
#     except ValueError:
#         try:
#             # Case 2: "YYYY-MM-DDTHH:MM:SSZ"
#             dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
#         except ValueError as e:
#             raise ValueError(f"Unsupported date format: {date_str}") from e

#     return int(dt.replace(tzinfo=timezone.utc).timestamp()) * 1000

def get_weather(city: str):
    """Generate random weather conditions for a given city."""
    temp = random.randint(10, 40)
    conditions = random.choice(["sunny", "cloudy", "rainy", "windy"])
    return f"The weather in {city} is {temp}°C and {conditions}."



def add_contact(name: str, email: str, phone: str, booked: str, t: str, date: str, role: str, cause: str, address: str, property_type: str, property_details: str):
    """
    Add or update a contact in GoHighLevel with custom fields.
    If the contact with the same email or phone exists, overwrite its info.
    """
    print(f"Adding/updating contact: {name}, {email}, {phone}, {booked}, {t}, {date}, {role}, {cause}, {address}, {property_type}, {property_details}", flush=True)
    if not(str(date).lower() == "cancelled" or str(t).lower() == "cancelled"):
        try:
            dt_str = f"{date} {t}"
            
            # Parse as UTC
            dt_utc = datetime.strptime(dt_str, "%d-%b-%Y %I:%M %p").replace(tzinfo=ZoneInfo("UTC"))
            iso_str = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")  # format to compare with slots

            # Build start and end of the same date (in UTC format)
            day = dt_utc.strftime("%Y-%m-%d")
            start = f"{day} 00:00:00"
            end = f"{day} 23:59:59"
            print(f"Checking availability for {iso_str} between {start} and {end}", flush=True)
            # Get available slots for that date
            available = get_available_time_slots(start, end)
            print("\nAvailable slots response:\n", flush=True)
            print(available, flush=True)
            # slots = available.get("data", {}).get(str(day), {}).get("slots", [])
            data_str = available.get("data", "{}")
            data_dict = json.loads(data_str)
            slots = data_dict.get(str(day), {}).get("slots", [])

            # Check availability
            if iso_str not in slots:
                print("\nIso string response:\n", flush=True)
                print(iso_str, "  ", slots, flush=True)
                # Create a "dummy" contact structure to prevent the calling function from crashing.
                # The 'message' will be passed to the next AI call to inform the user.
                # The key is providing a customField list with 3 elements to avoid the index error.
                error_payload = {
                    "status": "error",
                    "message": f"Sorry, the slot {date} {t} has already been taken.",
                    "data": {
                        "contact": {
                            "customField": [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}] # This safely fills the list
                        }
                    }
                }
                print(f"Slot {date} {t} not available.", flush=True)
                return error_payload
            # Convert to PDT
            print("\nDate and time before timezone conversion:\n", flush=True)
            print(date, " ", t, "\n", flush=True)
            dt_pdt = dt_utc.astimezone(ZoneInfo("America/New_York"))
            
            # Format back
            new_date = dt_pdt.strftime("%d-%b-%Y").upper()   # e.g. "21-OCT-2021"
            new_time = dt_pdt.strftime("%I:%M %p")   
            print("\nDate and time after timezone conversion:\n", flush=True)
            print(new_date, " ", new_time, "\n", flush=True)
        except Exception as e:
            print(f"Error processing date/time: {e}", flush=True)
            new_date = "cancelled"
            new_time = "cancelled"
            error_payload = {
                    "status": "error",
                    "message": f"Sorry an exception occurred: {str(e)}",
                    "data": {
                        "contact": {
                            "customField": [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}] # This safely fills the list
                        }
                    }
                }
            print(f"{t}, {date}", flush=True)
            return error_payload
        else:
            pass
    else:
        new_date = "cancelled"
        new_time = "cancelled"


    # Split name into first/last
    parts = name.strip().split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    # Lookup contact by email or phone
    lookup_url = f"{GHL_URL}/lookup"
    params = {}
    if email:
        params["email"] = email
    elif phone:
        params["phone"] = phone

    lookup_res = requests.get(lookup_url, headers=HEADERS, params=params)

    payload = {
        "firstName": first_name,
        "lastName": last_name,
        "email": email,
        "phone": phone,
        "customField": {
            BOOKED_FIELD_ID: booked,
            TIME_FIELD_ID: new_time,
            DATE_FIELD_ID: new_date,
            ROLE_FIELD_ID: role,  # Default to "Buyer"
            CAUSE_FIELD_ID: cause,  # Default to "N/A"
            ADDRESS_FIELD_ID: address,  # Default to "N/A"
            PROPERTY_TYPE_FIELD_ID: property_type,  # Default to "N/A"
            PROPERTY_DETAILS_FIELD_ID: property_details,  # Default to "N/A"

        }
    }

    if lookup_res.status_code == 200 and lookup_res.json().get("contact"):
        # Contact exists → update
        contact_id = lookup_res.json()["contact"]["id"]
        update_url = f"{GHL_URL}/{contact_id}"
        response = requests.put(update_url, headers=HEADERS, json=payload)
    else:
        # Contact doesn’t exist → create
        response = requests.post(GHL_URL, headers=HEADERS, json=payload)

    if response.status_code in (200, 201):
        return {"status": "success", "data": response.json()}
    else:
        return {"status": "error", "code": response.status_code, "message": response.text}
    

def save_conversation(conversation, name=None, email=None, phone=None, booked=None, contact_id=None, t=None, date=None):
    """
    Find contact in GHL, then save conversation to MongoDB.
    Overwrites old conversation if contact_id already exists.
    """
    if contact_id:
        conversations_col.update_one(
            {"contact_id": contact_id},
            {"$set": {"conversation": conversation}},
            upsert=True
        )
        print(f"Conversation saved in MongoDB for contact_id {contact_id}", flush=True)
        return
    else:
        if not conversation or (not email and not phone):
            print("Missing required info: conversation and either email or phone must be provided.", flush=True)
            return

        # Step 1: Search for the contact in GHL
        params = {}
        if email:
            params["email"] = email
        if phone:
            params["phone"] = phone

        search_resp = requests.get(GHL_URL, headers=HEADERS, params=params)

        if search_resp.status_code != 200:
            print(f"Error searching contact: {search_resp.text}", flush=True)
            return

        contacts = search_resp.json().get("contacts", [])
        if not contacts:
            print("No contact found with provided details.", flush=True)
            return

        contact_id = contacts[0]["id"]
        print(f"Found contact_id, line 194, in tools.py: {contact_id}", flush=True)

        # Step 2: Upsert conversation (overwrite if exists)
        conversations_col.update_one(
            {"contact_id": contact_id},
            {"$set": {"conversation": conversation}},
            upsert=True
        )

        print(f"Conversation saved in MongoDB for contact_id {contact_id}", flush=True)


def get_conversation(contact_id):
    """
    Retrieve only the conversation string for a given contact_id.
    Returns None if not found.
    """
    doc = conversations_col.find_one({"contact_id": contact_id}, {"_id": 0, "conversation": 1})
    return doc["conversation"] if doc else None



def get_available_time_slots(start_date: str, end_date: str) -> dict:
    """
    Fetch available time slots from GoHighLevel between given start and end dates.

    Args:
        start_date (str): Start date in ISO format (e.g., "2025-08-30T10:00:00Z").
        end_date (str): End date in ISO format (e.g., "2025-09-06T10:00:00Z").

    Returns:
        dict: Response with status, and either time slots (on success) or error info.
    """
    GHL_TOKEN = os.getenv("GHL_API_KEY")
    s = str(to_unix(start_date))
    e = str(to_unix(end_date))
    print(s + " ", e, flush=True)
    conn = http.client.HTTPSConnection("services.leadconnectorhq.com")
    payload = ''
    headers = {
    'Accept': 'application/json',
    'Version': '2021-04-15',
    'Authorization': 'Bearer ' + GHL_TOKEN
    }
    conn.request("GET", f"/calendars/JzIjRCGcT0ub3anLQjai/free-slots?startDate={s}&endDate={e}&timezone=UTC", payload, headers)
    res = conn.getresponse()
    data = res.read()
    print(data.decode("utf-8"), flush=True)
    if res.status == 200:
        return {"status": "success", "data": str(data.decode("utf-8"))}
    else:
        return {"status": "error", "code": res.status, "message": str(data.decode("utf-8"))}
    

def get_current_utc_datetime() -> str:
    """
    Get the current date and time in UTC and for the next 7 days.

    Returns:
        str: Contains the current UTC datetime and the date and day for the next 7 days.
    """
    now = datetime.now(timezone.utc)
    
    # Start with the current time info
    response_parts = [
        f"The current iso time is {now.isoformat()}",
        f"the unix timestamp is {int(now.timestamp())}",
        f"the normal one is {now.strftime('%Y-%m-%d %H:%M:%S')} in the format 'YYYY-MM-DD HH:MM:SS' (UTC)",
        f"and the day is {now.strftime('%A')}."
    ]

    # Add info for the next 7 days
    for i in range(1, 8):
        future_date = now + timedelta(days=i)
        day_name = future_date.strftime('%A')
        date_str = future_date.strftime('%Y-%m-%d')
        
        if i == 1:
            day_prefix = "Tomorrow"
        else:
            day_prefix = f"In {i} days"
            
        response_parts.append(f"{day_prefix} is {date_str} and it's a {day_name}.")

    return " ".join(response_parts)

# # save_conversation(contact_id="eWVjjelB67z7cbrlKkO5", conversation="This is a test conversation.")
print(get_current_utc_datetime())

# print(get_available_time_slots("2025-08-31 10:00:00", "2025-09-06 10:00:00"))
def get_contact_info(contact_id: str):
    conn = http.client.HTTPSConnection("services.leadconnectorhq.com")
    payload = ''
    headers = {
    'Accept': 'application/json',
    'Version': '2021-07-28',
    'Authorization': f'Bearer {API_KEY}'
    }
    conn.request("GET", f"/contacts/{contact_id}", payload, headers)
    res = conn.getresponse()
    data = res.read()
    print(data.decode("utf-8"))

# get_contact_info("EvY019lK4vcvjzsNTp9F")
# get_available_time_slots("2025-09-10 00:00:00", "2025-09-10 23:59:00")
# resp = get_available_time_slots("2025-09-10T00:00:00Z", "2025-09-10T23:59:59Z")
# get_available_time_slots("2025-09-10 00:00:00","2025-09-10 23:59:59" )


def replace_dynamic_variables(template, data):
    template = template.replace("_USER_NAME_", data.name if data.name else "")  # Replace newlines with spaces
    template = template.replace("_USER_EMAIL_", data.email if data.email else "")
    template = template.replace("_USER_PHONE_", data.phone if data.phone else "")
    template = template.replace("_MEETING_NOTES_", data.notes if data.notes else "")
    template = template.replace("_MEETING_DATE_", data.date if data.date else "")
    template = template.replace("_MEETING_TIME_", data.time if data.time else "")
    template = template.replace("_CURRENT_TIME_", get_current_utc_datetime())

    return template

# print(get_conversation("eWVjjelB67z7cbrlKkO5"))