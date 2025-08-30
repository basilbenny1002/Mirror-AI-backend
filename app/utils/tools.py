import random
# from database.insights_db import save_insight, search_insight
import os
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime
import http.client
import json
from datetime import datetime, timezone


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
BOOKED_FIELD_ID = "r9wLa2H8weqkXfIHgmLA"        # e.g. "Booked Call" field
TIME_FIELD_ID = "Ogr5kUZzwCTtMXQxMf17"          # e.g. "Call Time" field
DATE_FIELD_ID = "SMDVlM8yUR534vvOPkjn"          # e.g. "Call Date" field


def to_unix(date_str: str) -> int:
    """
    Convert a string in 'YYYY-MM-DD HH:MM:SS' format (UTC) to Unix timestamp (seconds).
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    # Treat it as UTC
    return int(dt.replace(tzinfo=timezone.utc).timestamp())

def get_weather(city: str):
    """Generate random weather conditions for a given city."""
    temp = random.randint(10, 40)
    conditions = random.choice(["sunny", "cloudy", "rainy", "windy"])
    return f"The weather in {city} is {temp}°C and {conditions}."

def add_contact(name: str, email: str, phone: str, booked: str, t: str, date: str):
    """
    Add a contact to GoHighLevel with custom fields.
    """

    # Split name into first/last
    parts = name.strip().split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    payload = {
        "firstName": first_name,
        "lastName": last_name,
        "email": email,
        "phone": phone,
        "customField": {
            BOOKED_FIELD_ID: booked,
            TIME_FIELD_ID: t,
            DATE_FIELD_ID: date
        }
    }
    
    response = requests.post(GHL_URL, headers=HEADERS, json=payload)

    if response.status_code == 200:
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
        print(f"Conversation saved in MongoDB for contact_id {contact_id}")
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
            print(f"Error searching contact: {search_resp.text}")
            return

        contacts = search_resp.json().get("contacts", [])
        if not contacts:
            print("No contact found with provided details.")
            return

        contact_id = contacts[0]["id"]

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
    s = to_unix(start_date)
    e = to_unix(end_date)
    conn = http.client.HTTPSConnection("services.leadconnectorhq.com")
    payload = ''
    headers = {
    'Accept': 'application/json',
    'Version': '2021-04-15',
    'Authorization': 'Bearer ' + GHL_TOKEN
    }
    conn.request("GET", "/calendars/3Y9CwpxIzqZgKUCXoyGc/free-slots?startDate=1756571400000&endDate=1757176200000&timezone=UTC", payload, headers)
    res = conn.getresponse()
    data = res.read()
    # print(data.decode("utf-8"))
    if res.status == 200:
        return {"status": "success", "data": str(data.decode("utf-8"))}
    else:
        return {"status": "error", "code": res.status, "message": str(data.decode("utf-8"))}


def get_current_utc_datetime() -> dict:
    """
    Get the current date and time in UTC.

    Returns:
        dict: Contains the current UTC datetime in both ISO 8601 format and Unix timestamp.
    """
    now = datetime.now(timezone.utc)
    return f"The current iso time is {now.isoformat()} and the unix timestamp is {int(now.timestamp())} and the normal one is {now.strftime('%Y-%m-%d %H:%M:%S')} in the fromat 'YYYY-MM-DD HH:MM:SS' (UTC). and the day is {now.strftime('%A')}"

# # save_conversation(contact_id="eWVjjelB67z7cbrlKkO5", conversation="This is a test conversation.")
# print(get_current_utc_datetime())

print(get_available_time_slots("2025-08-31 10:00:00", "2025-09-06 10:00:00"))