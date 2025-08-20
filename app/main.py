from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.chat import chat_session
from typing import Optional
from pydantic import BaseModel

app = FastAPI()

class ChatRequest(BaseModel):
    message: str    
    sessionID: str
    end: Optional[bool] = None


@app.get("/")
def root():
    return JSONResponse({"Status": "It works!"})


@app.post("/chat")
def chat(data: ChatRequest):
    try:
        return chat_session(data.sessionID, data.message, data.end if data.end else None )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

