import random
from database.insights_db import save_insight, search_insight

def get_weather(city: str):
    temp = random.randint(10, 40)
    conditions = random.choice(["sunny", "cloudy", "rainy", "windy"])
    return f"The weather in {city} is {temp}°C and {conditions}."

def save_insight_tool(insight: str):
    """
    Save an insight into the vector database.
    """
    save_insight("AI_SESSION", insight)  # session id could be dynamic
    return f"Insight saved: {insight}"

def search_insight_tool(query: str, n: int = 3):
    """
    Search for relevant past insights in the vector database.
    """
    results = search_insight(query, n=n)
    if not results:
        return "No relevant insights found."
    return " | ".join(results)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the weather for a given city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_insight_tool",
            "description": "Save an important insight into the vector database for later recall",
            "parameters": {
                "type": "object",
                "properties": {
                    "insight": {
                        "type": "string",
                        "description": "The insight text to save into the database"
                    }
                },
                "required": ["insight"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_insight_tool",
            "description": "Search for relevant past insights from the vector database",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The topic or question to look up"
                    },
                    "n": {
                        "type": "integer",
                        "description": "Number of top insights to return (default 3)"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

