import random
from database.insights_db import save_insight, search_insight
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GHL_API_KEY")

if not API_KEY:
    raise ValueError("GHL_API_KEY not found in .env file")

# Endpoint + headers
GHL_URL = "https://rest.gohighlevel.com/v1/contacts/"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Replace these with your actual custom field IDs
BOOKED_FIELD_ID = "abc12345"        # e.g. "Booked Call" field
CONVERSATION_FIELD_ID = "def67890"  # e.g. "Conversation Notes" field


def get_weather(city: str):
    """Generate random weather conditions for a given city."""
    temp = random.randint(10, 40)
    conditions = random.choice(["sunny", "cloudy", "rainy", "windy"])
    return f"The weather in {city} is {temp}°C and {conditions}."

def add_contact(name: str, email: str, phone: str, booked: str, conversation: str):
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
            CONVERSATION_FIELD_ID: conversation
        }
    }

    response = requests.post(GHL_URL, headers=HEADERS, json=payload)

    if response.status_code == 200:
        return {"status": "success", "data": response.json()}
    else:
        return {"status": "error", "code": response.status_code, "message": response.text}
    
def save_conversation(conversation, name=None, email=None, phone=None, booked=None):
    """
    Save a conversation note to an existing contact in GHL.
    Requires at least one unique identifier: email or phone.
    """

    if not conversation or (not email and not phone):
        print("Missing required info: conversation and either email or phone must be provided.")
        return

    # Step 1: Search for the contact
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

    contact_id = contacts[0]["id"]  # assuming first match is correct

    # Step 2: Update the conversation field
    payload = {
        "customField": {
            CONVERSATION_FIELD_ID: conversation
        }
    }

    update_url = f"{GHL_URL}{contact_id}"
    update_resp = requests.put(update_url, headers=HEADERS, json=payload)

    if update_resp.status_code == 200:
        print("Conversation saved successfully.")
        return update_resp.json()
    else:
        print(f"Failed to save conversation: {update_resp.text}")
        return None
