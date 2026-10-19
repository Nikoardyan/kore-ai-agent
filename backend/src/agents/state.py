"""
state.py - Definisi state untuk agent KORE AI.

Catatan arsitektur:
  Project ini menggunakan agent executor custom (di api.py: run_agent_executor),
  BUKAN LangGraph. AgentState di bawah ini adalah rancangan untuk migrasi ke
  LangGraph di masa depan (lihat Roadmap di README.md).

  Untuk saat ini, state percakapan dikelola lewat ChatRequest.recent_messages
  yang dikirim dari frontend.
"""

from typing import TypedDict, Annotated, Sequence, Optional
import operator

from src.schemas import ChatMessage


class AgentState(TypedDict):
    """
    State agent untuk implementasi LangGraph di masa depan.

    Fields:
        messages: Riwayat percakapan (user + assistant)
        current_step: Langkah agent saat ini (inspect, route, observe, respond)
        route: Jalur yang dipilih (database | rag | chat)
        topic: Topik database yang terdeteksi (leave, overtime, dll)
        employee_id: ID karyawan yang sedang login
        user_name: Nama tampilan karyawan
        final_reply: Jawaban akhir yang akan dikirim ke user
        source: Sumber jawaban (SQLite/PostgreSQL, PDF, Conversation)
    """
    messages: Annotated[Sequence[ChatMessage], operator.add]
    current_step: str
    route: Optional[str]
    topic: Optional[str]
    employee_id: Optional[str]
    user_name: Optional[str]
    final_reply: Optional[str]
    source: Optional[str]
