import random
# from database.insights_db import save_insight, search_insight
import os
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime

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


def get_weather(city: str):
    """Generate random weather conditions for a given city."""
    temp = random.randint(10, 40)
    conditions = random.choice(["sunny", "cloudy", "rainy", "windy"])
    return f"The weather in {city} is {temp}°C and {conditions}."

def add_contact(name: str, email: str, phone: str, booked: str):
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
        }
    }
    
    response = requests.post(GHL_URL, headers=HEADERS, json=payload)

    if response.status_code == 200:
        return {"status": "success", "data": response.json()}
    else:
        return {"status": "error", "code": response.status_code, "message": response.text}
    

def save_conversation(conversation, name=None, email=None, phone=None, booked=None, contact_id=None):
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
            print("Missing required info: conversation and either email or phone must be provided.")
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

        print(f"Conversation saved in MongoDB for contact_id {contact_id}")


def get_conversation(contact_id):
    """
    Retrieve only the conversation string for a given contact_id.
    Returns None if not found.
    """
    doc = conversations_col.find_one({"contact_id": contact_id}, {"_id": 0, "conversation": 1})
    return doc["conversation"] if doc else None


# save_conversation(contact_id="eWVjjelB67z7cbrlKkO5", conversation="This is a test conversation.")