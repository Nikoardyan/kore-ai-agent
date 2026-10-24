"""
agent.py - Core AI Agent runtime for KORE AI.
Menyediakan interface terpadu untuk menjalankan agent workflow (RAG, Database tools, Chat).
"""

from typing import Optional, List, Dict, Any
from src.schemas import ChatRequest, ChatMessage
from src.tools.leave_tools import get_leave_balance, list_leave_requests
from src.tools.rag_tools import retrieve_documents, answer_from_documents


class KoreAgent:
    """Agentic workspace runner yang mengintegrasikan tools, retrieval, dan reasoning."""

    def __init__(
        self,
        employee_id: Optional[str] = None,
        user_name: Optional[str] = None,
        role: str = "employee",
    ):
        self.employee_id = employee_id
        self.user_name = user_name
        self.role = role

    def ask(self, query: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """Menjalankan query melalui agent pipeline."""
        from api import run_agent_executor

        recent_messages = []
        if history:
            for h in history:
                recent_messages.append(
                    ChatMessage(
                        role="assistant" if h.get("role") in ["assistant", "ai"] else "user",
                        content=h.get("content", ""),
                        source=h.get("source"),
                    )
                )

        req = ChatRequest(
            message=query,
            user_name=self.user_name,
            employee_id=self.employee_id,
            requester_role=self.role,
            recent_messages=recent_messages,
        )
        return run_agent_executor(query, req)


def run_agent(query: str, employee_id: Optional[str] = None, user_name: Optional[str] = None) -> str:
    """Helper function sederhana untuk menjalankan agent secara langsung."""
    agent = KoreAgent(employee_id=employee_id, user_name=user_name)
    result = agent.ask(query)
    return result.get("reply", "")
