import json

from langchain_core.messages import HumanMessage, ToolMessage

from app.agent.graph import agent_graph

LOG_OR_EDIT_TOOLS = {"log_interaction", "edit_interaction"}


def run_agent(session_id: str, message: str) -> dict:
    """Run one turn of the LangGraph agent for the given chat session.

    Returns: {reply, tool_calls, interaction} where `interaction` is the
    latest interaction dict if a log_interaction/edit_interaction tool ran
    this turn (used by the frontend to sync the structured form).
    """
    config = {"configurable": {"thread_id": session_id}}
    result = agent_graph.invoke({"messages": [HumanMessage(content=message)]}, config=config)

    messages = result["messages"]
    tool_calls = []
    interaction = None

    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_calls.append(msg.name)
            if msg.name in LOG_OR_EDIT_TOOLS:
                try:
                    parsed = json.loads(msg.content)
                    if isinstance(parsed, dict) and "error" not in parsed:
                        interaction = parsed
                except (json.JSONDecodeError, TypeError):
                    pass

    reply = messages[-1].content if messages else ""
    return {"reply": reply, "tool_calls": tool_calls, "interaction": interaction}
