"""The five (+1) LangGraph tools available to the HCP interaction agent.

1. log_interaction        - create a new HCP interaction record (LLM entity extraction + summary)
2. edit_interaction       - modify an already-logged interaction (LLM patch extraction)
3. get_interaction_history- fetch past interactions for a given HCP (context for the rep/agent)
4. suggest_followups      - LLM-generated next-best-action suggestions for an interaction
5. schedule_followup      - persist a concrete follow-up task/reminder tied to an interaction
6. search_hcp             - look up / autocomplete known HCPs by name, specialty or institution
"""
import json
from typing import List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app import crud
from app.agent.extraction import extract_edit_patch, extract_interaction_entities, suggest_followups_llm
from app.database import SessionLocal


# ---------------------------------------------------------------------------
# 1. Log Interaction
# ---------------------------------------------------------------------------
class LogInteractionInput(BaseModel):
    raw_text: Optional[str] = Field(
        None,
        description="Free-text / conversational description of the interaction, e.g. "
        "'Met Dr. Sharma, discussed OncoBoost Phase III data, positive sentiment, shared brochure'. "
        "The LLM will extract structured fields from this. Use this OR the structured fields below.",
    )
    hcp_name: Optional[str] = Field(None, description="Name of the HCP, if already known.")
    interaction_type: Optional[str] = Field(None, description="Meeting | Call | Email | Conference | Virtual")
    date: Optional[str] = None
    time: Optional[str] = None
    attendees: Optional[List[str]] = None
    topics_discussed: Optional[str] = None
    materials_shared: Optional[List[str]] = None
    samples_distributed: Optional[List[str]] = None
    sentiment: Optional[str] = Field(None, description="Positive | Neutral | Negative")
    outcomes: Optional[str] = None
    follow_up_actions: Optional[str] = None


@tool("log_interaction", args_schema=LogInteractionInput)
def log_interaction(
    raw_text: Optional[str] = None,
    hcp_name: Optional[str] = None,
    interaction_type: Optional[str] = None,
    date: Optional[str] = None,
    time: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    topics_discussed: Optional[str] = None,
    materials_shared: Optional[List[str]] = None,
    samples_distributed: Optional[List[str]] = None,
    sentiment: Optional[str] = None,
    outcomes: Optional[str] = None,
    follow_up_actions: Optional[str] = None,
) -> str:
    """Log a new HCP interaction. If `raw_text` is given, the LLM extracts structured fields
    (HCP name, topics, sentiment, outcomes, follow-ups, materials/samples) and generates an
    AI summary. Any explicitly-provided structured fields override the extracted ones. Returns
    the created interaction as JSON."""
    extracted = extract_interaction_entities(raw_text) if raw_text else {}

    data = {
        "hcp_name": hcp_name or extracted.get("hcp_name") or "Unknown HCP",
        "interaction_type": interaction_type or extracted.get("interaction_type") or "Meeting",
        "date": date,
        "time": time,
        "attendees": attendees or [],
        "topics_discussed": topics_discussed or extracted.get("topics_discussed"),
        "materials_shared": materials_shared or extracted.get("materials_shared") or [],
        "samples_distributed": samples_distributed or extracted.get("samples_distributed") or [],
        "sentiment": sentiment or extracted.get("sentiment") or "Neutral",
        "outcomes": outcomes or extracted.get("outcomes"),
        "follow_up_actions": follow_up_actions or extracted.get("follow_up_actions"),
        "ai_summary": extracted.get("ai_summary"),
        "raw_input": raw_text,
    }

    db = SessionLocal()
    try:
        source = "chat" if raw_text else "form"
        interaction = crud.create_interaction(db, data, source=source)
        return json.dumps(crud.interaction_to_dict(interaction), default=str)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 2. Edit Interaction
# ---------------------------------------------------------------------------
class EditInteractionInput(BaseModel):
    interaction_id: str = Field(..., description="ID of the interaction to edit.")
    instruction: Optional[str] = Field(
        None, description="Free-text edit instruction, e.g. 'change sentiment to positive and add follow up to send samples'."
    )
    updates: Optional[dict] = Field(
        None, description="Explicit field->value updates, used instead of / in addition to `instruction`."
    )


@tool("edit_interaction", args_schema=EditInteractionInput)
def edit_interaction(interaction_id: str, instruction: Optional[str] = None, updates: Optional[dict] = None) -> str:
    """Modify a previously logged HCP interaction. Accepts either a free-text `instruction`
    (LLM converts it into a field patch) or an explicit `updates` dict, or both (explicit
    updates win on conflicts). Returns the updated interaction as JSON, or an error message."""
    db = SessionLocal()
    try:
        current = crud.get_interaction(db, interaction_id)
        if not current:
            return json.dumps({"error": f"No interaction found with id {interaction_id}"})

        patch = {}
        if instruction:
            patch.update(extract_edit_patch(crud.interaction_to_dict(current), instruction))
        if updates:
            patch.update(updates)

        updated = crud.update_interaction(db, interaction_id, patch)
        return json.dumps(crud.interaction_to_dict(updated), default=str)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3. Get Interaction History
# ---------------------------------------------------------------------------
class HistoryInput(BaseModel):
    hcp_name: str = Field(..., description="Name of the HCP whose past interactions should be retrieved.")
    limit: int = Field(5, description="Max number of past interactions to return.")


@tool("get_interaction_history", args_schema=HistoryInput)
def get_interaction_history(hcp_name: str, limit: int = 5) -> str:
    """Fetch the most recent past interactions logged for a given HCP, so the rep/agent has
    context (previous topics, sentiment trend, outstanding follow-ups) before logging a new
    one. Returns a JSON list of interactions."""
    db = SessionLocal()
    try:
        interactions = crud.list_interactions(db, hcp_name=hcp_name, limit=limit)
        return json.dumps([crud.interaction_to_dict(i) for i in interactions], default=str)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4. Suggest Follow-ups
# ---------------------------------------------------------------------------
class SuggestFollowupsInput(BaseModel):
    interaction_id: str = Field(..., description="ID of the interaction to generate follow-up suggestions for.")


@tool("suggest_followups", args_schema=SuggestFollowupsInput)
def suggest_followups(interaction_id: str) -> str:
    """Generate AI-suggested next-best-action follow-ups (e.g. schedule a meeting, send a
    specific brochure, add to an advisory board list) for a logged interaction, using the
    interaction content plus the HCP's interaction history. Returns a JSON list of suggestion
    strings."""
    db = SessionLocal()
    try:
        interaction = crud.get_interaction(db, interaction_id)
        if not interaction:
            return json.dumps({"error": f"No interaction found with id {interaction_id}"})

        history = crud.list_interactions(db, hcp_name=interaction.hcp.name, limit=5)
        history_summary = "\n".join(
            f"- {h.date or ''} {h.interaction_type}: {h.topics_discussed or ''} (sentiment: {h.sentiment})"
            for h in history
            if h.id != interaction_id
        )
        interaction_summary = (
            f"HCP: {interaction.hcp.name}\nType: {interaction.interaction_type}\n"
            f"Topics: {interaction.topics_discussed}\nSentiment: {interaction.sentiment}\n"
            f"Outcomes: {interaction.outcomes}\nSummary: {interaction.ai_summary}"
        )
        suggestions = suggest_followups_llm(interaction_summary, history_summary)
        return json.dumps({"interaction_id": interaction_id, "suggestions": suggestions})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5. Schedule Follow-up
# ---------------------------------------------------------------------------
class ScheduleFollowupInput(BaseModel):
    interaction_id: str = Field(..., description="ID of the interaction this follow-up relates to.")
    description: str = Field(..., description="What needs to be done, e.g. 'Send OncoBoost Phase III PDF'.")
    due_date: Optional[str] = Field(None, description="Due date for the follow-up, e.g. '2026-07-28'.")


@tool("schedule_followup", args_schema=ScheduleFollowupInput)
def schedule_followup(interaction_id: str, description: str, due_date: Optional[str] = None) -> str:
    """Persist a concrete follow-up task/reminder (e.g. 'schedule follow-up meeting in 2 weeks',
    'send OncoBoost Phase III PDF') tied to a logged interaction. Returns the created follow-up
    as JSON."""
    db = SessionLocal()
    try:
        interaction = crud.get_interaction(db, interaction_id)
        if not interaction:
            return json.dumps({"error": f"No interaction found with id {interaction_id}"})
        follow_up = crud.create_follow_up(db, interaction_id, description, due_date)
        return json.dumps(
            {
                "id": follow_up.id,
                "interaction_id": follow_up.interaction_id,
                "description": follow_up.description,
                "due_date": follow_up.due_date,
                "status": follow_up.status.value if hasattr(follow_up.status, "value") else follow_up.status,
            }
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 6. Search HCP
# ---------------------------------------------------------------------------
class SearchHCPInput(BaseModel):
    query: str = Field("", description="Partial name, specialty, or institution to search for.")


@tool("search_hcp", args_schema=SearchHCPInput)
def search_hcp(query: str = "") -> str:
    """Search/autocomplete known HCPs by name, specialty, or institution. Returns a JSON list
    of matching HCPs (id, name, specialty, institution)."""
    db = SessionLocal()
    try:
        hcps = crud.search_hcps(db, query)
        return json.dumps(
            [{"id": h.id, "name": h.name, "specialty": h.specialty, "institution": h.institution} for h in hcps]
        )
    finally:
        db.close()


ALL_TOOLS = [
    log_interaction,
    edit_interaction,
    get_interaction_history,
    suggest_followups,
    schedule_followup,
    search_hcp,
]
