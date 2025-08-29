from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.chat import chat_session, resume_chat_session
from typing import Optional
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  #["http://localhost:3000", "https://www.leadifysolutions.xyz", "http://www.leadifysolutions.xyz"] or ["*"] for all, but not safe for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class ChatRequest(BaseModel):
    message: str    
    sessionID: str
    end: Optional[bool] = None

class ResumeChat(BaseModel):
    id: str
    reply: Optional[str] = None
    followup_stage: str


@app.get("/")
def root():
    return JSONResponse({"Status": "It works!"})


@app.post("/chat")
def chat(data: ChatRequest):
    try:
        return chat_session(data.sessionID, data.message, data.end if data.end else None )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    
@app.post("/resume_chat")
def resume_chat(data: ResumeChat):
    try:
        return resume_chat_session(contactID=data.id, user_input=data.reply, followup_stage=data.followup_stage)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
