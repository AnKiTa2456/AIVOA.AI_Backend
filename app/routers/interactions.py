import json

from fastapi import APIRouter, HTTPException, Query

from app.agent.tools import edit_interaction, get_interaction_history, log_interaction, schedule_followup, suggest_followups
from app.schemas import InteractionCreate, InteractionUpdate

router = APIRouter(prefix="/api/interactions", tags=["interactions"])


@router.post("")
def create_interaction(payload: InteractionCreate):
    """Structured-form submission path. Still routes through the same LangGraph
    `log_interaction` tool used by the chat agent, so both entry points share one
    LLM-assisted persistence path."""
    result = json.loads(log_interaction.invoke(payload.model_dump()))
    return result


@router.get("")
def list_interactions(hcp_name: str | None = Query(default=None), limit: int = 20):
    result = json.loads(get_interaction_history.invoke({"hcp_name": hcp_name or "", "limit": limit}))
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.put("/{interaction_id}")
def update_interaction(interaction_id: str, payload: InteractionUpdate):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    result = json.loads(edit_interaction.invoke({"interaction_id": interaction_id, "updates": updates}))
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/{interaction_id}/followup-suggestions")
def get_followup_suggestions(interaction_id: str):
    result = json.loads(suggest_followups.invoke({"interaction_id": interaction_id}))
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/{interaction_id}/followups")
def create_followup(interaction_id: str, description: str, due_date: str | None = None):
    result = json.loads(
        schedule_followup.invoke({"interaction_id": interaction_id, "description": description, "due_date": due_date})
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
