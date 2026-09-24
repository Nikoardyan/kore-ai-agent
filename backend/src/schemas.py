from pydantic import BaseModel, Field
from typing import Optional

# Skema untuk Chat
class ChatMessage(BaseModel):
    role: str
    content: str
    source: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    user_name: Optional[str] = None
    employee_id: Optional[str] = None
    recent_messages: list[ChatMessage] = Field(default_factory=list)

class AgentStep(BaseModel):
    thought: str
    action: str
    observation: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    source: Optional[str] = None  # Dari mana jawaban ditemukan (misal: RAG, database, dll)
    agent_steps: list[AgentStep] = Field(default_factory=list)

class AuthRegisterRequest(BaseModel):
    employee_id: str
    password: str
    display_name: Optional[str] = None

class AuthLoginRequest(BaseModel):
    employee_id: str
    password: str

class AuthUser(BaseModel):
    employee_id: str
    display_name: Optional[str] = None

class AuthResponse(BaseModel):
    token: str
    user: AuthUser

# Skema permintaan kredit (contoh sebelumnya)
class CreditRequest(BaseModel):
    user_id: str
    amount: float
    income: float

class CreditResponse(BaseModel):
    approved: bool
    risk_score: float
    message: str
