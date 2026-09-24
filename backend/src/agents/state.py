from typing import TypedDict, Annotated, Sequence
import operator

# Contoh State untuk LangGraph
class AgentState(TypedDict):
    messages: Annotated[Sequence[str], operator.add]
    current_step: str
