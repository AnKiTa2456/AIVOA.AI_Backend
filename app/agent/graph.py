"""LangGraph StateGraph wiring for the HCP Interaction agent.

Flow:  START -> agent (Groq LLM bound to tools) -> tools_condition -> [tools -> agent | END]

The agent node decides, turn by turn, which of the 6 tools to call (log_interaction,
edit_interaction, get_interaction_history, suggest_followups, schedule_followup, search_hcp)
based on the conversation so far, executes them via the ToolNode, feeds the tool
results back to itself, and finally answers the rep in natural language.
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing import Annotated, TypedDict

from app.agent.llm import get_chat_llm
from app.agent.tools import ALL_TOOLS

SYSTEM_PROMPT = """You are the AI assistant embedded in a pharma field rep's CRM, on the \
"Log HCP Interaction" screen. Your job is to help the rep log, edit, and follow up on \
interactions with Healthcare Professionals (HCPs) via natural conversation, using the tools \
available to you.

Guidelines:
- If the rep describes an interaction in free text, call `log_interaction` with `raw_text` set \
  to their message so the details get extracted and saved.
- If the rep asks to change something about an already-logged interaction, use `edit_interaction` \
  (you need the interaction_id — ask for it or use the most recent one from context if clear).
- If the rep asks about a HCP's past visits/history, use `get_interaction_history`.
- After logging an interaction, proactively consider calling `suggest_followups` to propose next \
  steps, and `schedule_followup` if the rep confirms one.
- Use `search_hcp` to resolve ambiguous or partially-typed HCP names.
- Keep replies concise, professional, and specific to what a pharma field rep needs.
"""


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


def _agent_node(state: AgentState):
    llm = get_chat_llm().bind_tools(ALL_TOOLS)
    messages = state["messages"]
    if not messages or messages[0].type != "system":
        from langchain_core.messages import SystemMessage

        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
    response = llm.invoke(messages)
    return {"messages": [response]}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", _agent_node)
    graph.add_node("tools", ToolNode(ALL_TOOLS))

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


agent_graph = build_graph()
