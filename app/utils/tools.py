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