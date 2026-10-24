from typing import Literal, Optional

from pydantic import BaseModel, Field


MAX_MESSAGE_LENGTH = 2_000
MAX_HISTORY_MESSAGES = 12
MAX_HISTORY_MESSAGE_LENGTH = 2_000
MAX_PASSWORD_LENGTH = 256

# Skema untuk Chat
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_HISTORY_MESSAGE_LENGTH)
    source: Optional[str] = Field(default=None, max_length=256)

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    user_name: Optional[str] = Field(default=None, max_length=128)
    # Diabaikan oleh endpoint chat; identitas selalu diambil dari token.
    employee_id: Optional[str] = Field(default=None, max_length=64)
    requester_role: Optional[str] = Field(default=None, max_length=32)
    recent_messages: list[ChatMessage] = Field(default_factory=list, max_length=MAX_HISTORY_MESSAGES)

class AgentStep(BaseModel):
    thought: str
    action: str
    observation: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    source: Optional[str] = None  # Dari mana jawaban ditemukan (misal: RAG, database, dll)
    agent_steps: list[AgentStep] = Field(default_factory=list)

class AuthRegisterRequest(BaseModel):
    employee_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=12, max_length=MAX_PASSWORD_LENGTH)
    # Nama dari client tidak dipakai sebagai sumber otoritatif.
    display_name: Optional[str] = Field(default=None, max_length=128)

class AuthLoginRequest(BaseModel):
    employee_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)

class AuthUser(BaseModel):
    employee_id: str
    display_name: Optional[str] = None
    role: str = "employee"

class AuthResponse(BaseModel):
    token: str
    user: AuthUser
