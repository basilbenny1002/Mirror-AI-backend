# # import os
# # import random
# # import json
# # import time
# # from dotenv import load_dotenv
# # from openai import OpenAI

# # # Load environment variables
# # load_dotenv()
# # api_key = os.getenv("OPEN_AI_API_KEY")
# # if not api_key:
# #     raise ValueError("OPEN_AI_API_KEY not found in .env file. Ensure .env contains: OPEN_AI_API_KEY=your-api-key-here")

# # # Initialize OpenAI client
# # client = OpenAI(api_key=api_key)

# # # Debug: Check if vector_stores is available
# # try:
# #     hasattr(client.beta, "vector_stores")
# #     print("vector_stores attribute is available.")
# # except AttributeError:
# #     print("Warning: vector_stores attribute is not available in this OpenAI version.")

# # # Upload the PDF file
# # pdf_path = "LeadifySolutions_Info_FULL.pdf"
# # if not os.path.exists(pdf_path):
# #     raise FileNotFoundError(f"PDF file not found at {pdf_path}")

# # try:
# #     file = client.files.create(
# #         file=open(pdf_path, "rb"),
# #         purpose="assistants"
# #     )
# # except Exception as e:
# #     raise Exception(f"Failed to upload PDF: {str(e)}")

# # # System instructions
# # instructions = """
# # You are a helpful assistant. Use the following information from the PDF to answer user questions.
# # """

# # # Define the get_weather tool
# # weather_tool = {
# #     "type": "function",
# #     "function": {
# #         "name": "get_weather",
# #         "description": "Get weather for a given city",
# #         "parameters": {
# #             "type": "object",
# #             "properties": {
# #                 "city": {
# #                     "type": "string",
# #                     "description": "City name"
# #                 }
# #             },
# #             "required": ["city"]
# #         }
# #     }
# # }

# # # Create the assistant
# # try:
# #     assistant = client.beta.assistants.create(
# #         name="Website Assistant",
# #         instructions=instructions,
# #         model="gpt-4o-mini",
# #         tools=[
# #             {"type": "file_search"},
# #             weather_tool
# #         ]
# #     )
# # except Exception as e:
# #     raise Exception(f"Failed to create assistant: {str(e)}")

# # # Storage for sessions (session_id to thread_id and file_id)
# # sessions = {}

# # def get_weather(city: str):
# #     """Generate random weather conditions for a given city."""
# #     temp = random.randint(10, 40)
# #     conditions = random.choice(["sunny", "cloudy", "rainy", "windy"])
# #     return f"The weather in {city} is {temp}°C and {conditions}."

# # def chat_session(session_id: str, user_input: str, end: bool = False):
# #     """Manage a chat session.
    
# #     Args:
# #         session_id: Unique identifier for the chat
# #         user_input: User text prompt
# #         end: If True, close the chat and return final response
# #     """
# #     if end:
# #         if session_id in sessions:
# #             try:
# #                 client.beta.threads.delete(thread_id=sessions[session_id]["thread_id"])
# #                 del sessions[session_id]
# #             except Exception as e:
# #                 return f"Error ending session: {str(e)}"
# #         return "Chat session ended."

# #     if session_id not in sessions:
# #         try:
# #             thread = client.beta.threads.create()
# #             sessions[session_id] = {"thread_id": thread.id, "file_id": file.id}
# #         except Exception as e:
# #             return f"Error creating session: {str(e)}"

# #     thread_id = sessions[session_id]["thread_id"]
# #     file_id = sessions[session_id]["file_id"]

# #     # Add user message with file attachment for file search
# #     try:
# #         client.beta.threads.messages.create(
# #             thread_id=thread_id,
# #             role="user",
# #             content=user_input,
# #             attachments=[{"file_id": file_id, "tools": [{"type": "file_search"}]}] if "services" in user_input.lower() or "policy" in user_input.lower() else []
# #         )
# #     except Exception as e:
# #         return f"Error adding message: {str(e)}"

# #     # Run the assistant
# #     try:
# #         run = client.beta.threads.runs.create(
# #             thread_id=thread_id,
# #             assistant_id=assistant.id
# #         )
# #     except Exception as e:
# #         return f"Error running assistant: {str(e)}"

# #     # Poll for completion
# #     max_attempts = 30
# #     attempt = 0
# #     while attempt < max_attempts:
# #         time.sleep(1)
# #         try:
# #             run = client.beta.threads.runs.retrieve(
# #                 thread_id=thread_id,
# #                 run_id=run.id
# #             )
# #         except Exception as e:
# #             return f"Error retrieving run status: {str(e)}"

# #         if run.status == "completed":
# #             break
# #         elif run.status == "requires_action":
# #             tool_outputs = []
# #             for tool_call in run.required_action.submit_tool_outputs.tool_calls:
# #                 if tool_call.type == "function" and tool_call.function.name == "get_weather":
# #                     try:
# #                         args = json.loads(tool_call.function.arguments)
# #                         result = get_weather(args["city"])
# #                         tool_outputs.append({
# #                             "tool_call_id": tool_call.id,
# #                             "output": result
# #                         })
# #                     except Exception as e:
# #                         return f"Error processing tool call: {str(e)}"

# #             if tool_outputs:
# #                 try:
# #                     client.beta.threads.runs.submit_tool_outputs(
# #                         thread_id=thread_id,
# #                         run_id=run.id,
# #                         tool_outputs=tool_outputs
# #                     )
# #                 except Exception as e:
# #                     return f"Error submitting tool outputs: {str(e)}"
# #         attempt += 1

# #     if run.status != "completed":
# #         return "Assistant did not complete the response in time."

# #     # Get the latest assistant message
# #     try:
# #         messages = client.beta.threads.messages.list(
# #             thread_id=thread_id,
# #             limit=1
# #         )
# #         if messages.data and messages.data[0].role == "assistant":
# #             response = messages.data[0].content[0].text.value
# #         else:
# #             response = "No response generated."
# #     except Exception as e:
# #         return f"Error retrieving messages: {str(e)}"

# #     return response

# # # Test the chatbot
# # if __name__ == "__main__":
# #     session_id = "test_session"
# #     print("Chatbot ready. Type 'exit' to end.")
# #     while True:
# #         user_input = input("You: ")
# #         if user_input.lower() == "exit":
# #             print(chat_session(session_id, "", end=True))
# #             break
# #         response = chat_session(session_id, user_input)
# #         print("Assistant:", response)



# import os
# import random
# import json
# import time
# from dotenv import load_dotenv
# from openai import OpenAI
# import PyPDF2

# # Load environment variables
# load_dotenv()
# api_key = os.getenv("OPEN_AI_API_KEY")
# if not api_key:
#     raise ValueError("OPEN_AI_API_KEY not found in .env file. Ensure .env contains: OPEN_AI_API_KEY=your-api-key-here")

# # Initialize OpenAI client
# client = OpenAI(api_key=api_key)

# # Extract text from the PDF file
# pdf_path = "LeadifySolutions_Info_FULL.pdf"
# if not os.path.exists(pdf_path):
#     raise FileNotFoundError(f"PDF file not found at {pdf_path}")

# try:
#     with open(pdf_path, "rb") as file:
#         pdf_reader = PyPDF2.PdfReader(file)
#         pdf_text = ""
#         for page in pdf_reader.pages:
#             extracted_text = page.extract_text()
#             if extracted_text:
#                 pdf_text += extracted_text + "\n"
#         if not pdf_text:
#             raise ValueError("No text could be extracted from the PDF.")
# except Exception as e:
#     raise Exception(f"Failed to process PDF: {str(e)}")

# # System instructions
# instructions = f"""You are a helpful assistant. Use the following information from the PDF to answer user questions. info {pdf_text}"""


# # Define the get_weather tool
# weather_tool = {
#     "type": "function",
#     "function": {
#         "name": "get_weather",
#         "description": "Get weather for a given city",
#         "parameters": {
#             "type": "object",
#             "properties": {
#                 "city": {
#                     "type": "string",
#                     "description": "City name"
#                 }
#             },
#             "required": ["city"]
#         }
#     }
# }

# # Storage for sessions (session_id to conversation history)
# sessions = {}

# def get_weather(city: str):
#     """Generate random weather conditions for a given city."""
#     temp = random.randint(10, 40)
#     conditions = random.choice(["sunny", "cloudy", "rainy", "windy"])
#     return f"The weather in {city} is {temp}°C and {conditions}."

# def chat_session(session_id: str, user_input: str, end: bool = False):
#     """Manage a chat session.
    
#     Args:
#         session_id: Unique identifier for the chat
#         user_input: User text prompt
#         end: If True, close the chat and return final response
#     """
#     if end:
#         if session_id in sessions:
#             del sessions[session_id]
#         return "Chat session ended."

#     if session_id not in sessions:
#         sessions[session_id] = {
#             "messages": [
#                 {"role": "system", "content": instructions}
#             ]
#         }

#     # Add user message to session history
#     sessions[session_id]["messages"].append({
#         "role": "user",
#         "content": user_input
#     })

#     # Prepare the API request
#     try:
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=sessions[session_id]["messages"],
#             tools=[weather_tool],
#             tool_choice="auto"
#         )
#     except Exception as e:
#         return f"Error calling chat completion: {str(e)}"

#     # Process the response
#     choice = response.choices[0]
#     if choice.finish_reason == "tool_calls":
#         tool_calls = choice.message.tool_calls
#         tool_messages = []
#         for tool_call in tool_calls:
#             if tool_call.type == "function" and tool_call.function.name == "get_weather":
#                 try:
#                     args = json.loads(tool_call.function.arguments)
#                     result = get_weather(args["city"])
#                     tool_messages.append({
#                         "role": "tool",
#                         "content": result,
#                         "tool_call_id": tool_call.id
#                     })
#                 except Exception as e:
#                     return f"Error processing tool call: {str(e)}"

#         # Append assistant message (without tool_calls) to history
#         sessions[session_id]["messages"].append({
#             "role": "assistant",
#             "content": choice.message.content or ""
#         })

#         # Append tool response messages to history
#         sessions[session_id]["messages"].extend(tool_messages)

#         # Submit tool outputs and get final response
#         try:
#             final_response = client.chat.completions.create(
#                 model="gpt-4o-mini",
#                 messages=sessions[session_id]["messages"],
#                 tools=[weather_tool],
#                 tool_choice="auto"
#             )
#             response_message = final_response.choices[0].message.content
#         except Exception as e:
#             return f"Error submitting tool outputs: {str(e)}"
#     else:
#         response_message = choice.message.content

#     # Append final assistant response to session history
#     sessions[session_id]["messages"].append({
#         "role": "assistant",
#         "content": response_message
#     })

#     return response_message

# # Test the chatbot
# if __name__ == "__main__":
#     session_id = "test_session"
#     print("Chatbot ready. Type 'exit' to end.")
#     while True:
#         user_input = input("You: ")
#         if user_input.lower() == "exit":
#             print(chat_session(session_id, "", end=True))
#             break
#         response = chat_session(session_id, user_input)
#         print("Assistant:", response)

# from datetime import datetime

# # Get the current date and time
# current_datetime = datetime.now()

# # Print the current date and time in its default format (YYYY-MM-DD HH:MM:SS.microseconds)
# print("Current Date and Time:", current_datetime)

import http.client

conn = http.client.HTTPSConnection("services.leadconnectorhq.com")
payload = ''
headers = {
  'Accept': 'application/json',
  'Version': '2021-04-15',
  'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJsb2NhdGlvbl9pZCI6InRQak5RcmYwcHFiSUVTcGU3T25rIiwidmVyc2lvbiI6MSwiaWF0IjoxNzU2MDU5MjYxNDQ0LCJzdWIiOiJQY2RKSkliMlJ0RFhiN0F3Y2VudiJ9.FEYh5MkPpB7xKSTV39ynfhXiRaBn_RBp1NZACJYBaT8'
}
conn.request("GET", "/calendars/3Y9CwpxIzqZgKUCXoyGc/free-slots?startDate=1756571400000&endDate=1757176200000&timezone=UTC", payload, headers)
res = conn.getresponse()
data = res.read()
print(data.decode("utf-8"))