import os
import random
from dotenv import load_dotenv
from openai import OpenAI

# Load .env
load_dotenv()
api_key = os.getenv("OPEN_AI_API_KEY")

client = OpenAI(api_key=api_key)

# Define our fake weather tool
def get_weather(city: str):
    # Just generate fake random weather
    temp = random.randint(10, 40)
    conditions = random.choice(["sunny", "cloudy", "rainy", "windy"])
    return f"The weather in {city} is {temp}°C and {conditions}."

# Conversation history
messages = [
    {"role": "system", "content": "You are a helpful assistant. If you need weather info, call the tool 'get_weather'."}
]

print("Chatbot ready! Type 'quit' to exit.\n")

while True:
    user_input = input("You: ")
    if user_input.lower() in ["quit", "exit"]:
        break

    # Add user input
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

    # If tool call
    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            args = eval(tool_call.function.arguments)  # careful: in prod use json.loads
            if fn_name == "get_weather":
                result = get_weather(args["city"])
                # Add tool result back to conversation
                messages.append({"role": "assistant", "content": None, "tool_calls": msg.tool_calls})
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})

                # Get final model response after tool execution
                followup = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages
                )
                final_msg = followup.choices[0].message.content
                print(f"AI: {final_msg}")
                messages.append({"role": "assistant", "content": final_msg})
    else:
        # Normal response
        ai_response = msg.content
        print(f"AI: {ai_response}")
        messages.append({"role": "assistant", "content": ai_response})
