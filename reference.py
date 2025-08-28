# from google import genai
# from google.genai import types
# import random
# import json
# import os
# from dotenv import load_dotenv


# # --- Initialization Stuff (Unchanged, as you requested) ---
# load_dotenv()

# def getWeather(location: str) -> str:
#     """
#     Gets the current temperature for a given location.
#     In a real application, this would call a weather API.
#     For this example, it returns random data.
#     """
#     print(f"--- Tool: Calling get_current_temperature for location: {location} ---")
#     weather_conditions = ["Sunny", "Cloudy", "Rainy", "Snowy", "Windy", "Partly Cloudy"]
#     temperature = random.randint(-5, 35)
#     return json.dumps({
#         "location": location,
#         "temperature": f"{temperature}°C",
#         "condition": random.choice(weather_conditions)
#     })

# # Define the function declaration for the model
# weather_function = {
#     "name": "getWeather",
#     "description": "Gets the current temperature for a given location.",
#     "parameters": {
#         "type": "object",
#         "properties": {
#             "location": {
#                 "type": "string",
#                 "description": "The city name, e.g. San Francisco",
#             },
#         },
#         "required": ["location"],
#     },
# }



# # Configure the client and tools
# key = os.getenv("GEMINI_API_KEY")
# client = genai.Client(api_key=key) # Using your original client
# tools = types.Tool(function_declarations=[weather_function])
# config = types.GenerateContentConfig(tools=[tools])

# # --- Start of Conversational Loop ---
# # We will manually manage the conversation history in a list
# history = []
# print(" I am a helpful assistant. Ask me about the weather! (Type 'exit' to quit)")

# while True:
#     # Get user input
#     user_input = input("You: ")
#     if user_input.lower() == 'exit':
#         print(history)
#         print("Goodbye!")
#         break

#     # Add the user's message to the history
#     history.append(types.Content(parts=[types.Part(text=user_input)], role="user"))

#     # Send the entire history to the model
#     response = client.models.generate_content(
#         model="gemini-2.5-flash", # Changed to a model that supports this client
#         contents=history,
#         config=config,
#     )

#     # The response from the model is the last message in the candidate
#     with open("response.txt", "w") as f:
#         f.write(str(response))
#     model_response_part = response.candidates[0].content.parts[0]
    
#     # Check if the model wants to call the function
#     if model_response_part.function_call:
#         # --- This is the two-step function calling process ---
#         function_call = model_response_part.function_call
#         print(function_call)
#         try:
#             print(eval(f"{function_call.name}({function_call.args})"))
#         except Exception as e:
#             print(f"Error calling function {function_call.name}: {e}")
#             continue
#         print(f"Gemini wants to call function: {function_call.name} with args: {function_call.args}")
        
#         # 1. Call the actual Python function with the arguments from the model
#         result = getWeather(**function_call.args)
        
#         # Add the model's function call request to history
#         history.append(types.Content(parts=[model_response_part], role="model"))
        
#         # 2. Send the function's result back to the model
#         history.append(
#             types.Content(
#                 parts=[
#                     types.Part.from_function_response(
#                         name="get_current_temperature",
#                         response={"content": result},
#                     )
#                 ],
#                 role="function",
#             )
#         )
        
#         # Get the final, natural language response from the model
#         final_response = client.models.generate_content(
#             model="gemini-2.5-flash",
#             contents=history,
#             config=config,
#         )
#         final_text = final_response.candidates[0].content.parts[0].text
#         print(f"Gemini: {final_text}")
#         # Add the final text response to history for context in the next turn
#         history.append(final_response.candidates[0].content)

#     else:
#         # If it's a regular text response, just print it
#         text_response = model_response_part.text
#         print(f"Gemini: {text_response}")
#         # Add the model's response to history
#         history.append(response.candidates[0].content)

    