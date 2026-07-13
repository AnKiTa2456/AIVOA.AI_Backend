"""LLM-backed helpers for turning free text into structured interaction data.

Used by the `log_interaction` and `edit_interaction` tools so that a rep can
just type/speak a sentence like:
  "Met Dr. Sharma, discussed OncoBoost Phase III data, she was positive,
   shared the brochure, follow up in 2 weeks"
and get a fully structured, database-ready record.
"""
import json
import re
from datetime import date

from app.agent.llm import invoke_with_fallback

EXTRACTION_SYSTEM_PROMPT = """You are a life-sciences CRM assistant that extracts structured data \
from a field representative's free-text description of a Healthcare Professional (HCP) interaction.

Return ONLY a valid JSON object (no markdown fences, no commentary) with these keys:
- hcp_name (string, best guess of the HCP's name, e.g. "Dr. Sharma")
- interaction_type (one of: "Meeting", "Call", "Email", "Conference", "Virtual")
- topics_discussed (short string summarizing what was discussed)
- sentiment (one of: "Positive", "Neutral", "Negative" — the HCP's observed sentiment)
- outcomes (short string of agreed outcomes, empty string if none mentioned)
- follow_up_actions (short string of next steps, empty string if none mentioned)
- materials_shared (list of strings — brochures/decks/PDFs mentioned, [] if none)
- samples_distributed (list of strings — drug/product samples mentioned, [] if none)
- ai_summary (one crisp sentence summarizing the whole interaction)

If a field cannot be inferred, use a sensible empty default. Today's date is {today}.
"""


def _parse_json_block(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def extract_interaction_entities(raw_text: str) -> dict:
    messages = [
        ("system", EXTRACTION_SYSTEM_PROMPT.format(today=date.today().isoformat())),
        ("user", raw_text),
    ]
    response = invoke_with_fallback(messages, temperature=0.1)
    try:
        return _parse_json_block(response.content)
    except (json.JSONDecodeError, AttributeError):
        return {
            "hcp_name": "Unknown HCP",
            "interaction_type": "Meeting",
            "topics_discussed": raw_text,
            "sentiment": "Neutral",
            "outcomes": "",
            "follow_up_actions": "",
            "materials_shared": [],
            "samples_distributed": [],
            "ai_summary": raw_text[:200],
        }


EDIT_SYSTEM_PROMPT = """You are a life-sciences CRM assistant. A field rep wants to amend an \
already-logged HCP interaction using a free-text instruction. Given the CURRENT record (JSON) and \
the rep's EDIT INSTRUCTION, return ONLY a JSON object containing just the fields that should change \
(a partial patch). Valid keys are exactly: interaction_type, date, time, attendees, topics_discussed, \
materials_shared, samples_distributed, sentiment, outcomes, follow_up_actions. \
Do not include keys that are not changing. No markdown fences, no commentary.
"""


def extract_edit_patch(current_record: dict, instruction: str) -> dict:
    messages = [
        ("system", EDIT_SYSTEM_PROMPT),
        ("user", f"CURRENT RECORD:\n{json.dumps(current_record, default=str)}\n\nEDIT INSTRUCTION:\n{instruction}"),
    ]
    response = invoke_with_fallback(messages, temperature=0.1)
    try:
        return _parse_json_block(response.content)
    except (json.JSONDecodeError, AttributeError):
        return {}


FOLLOWUP_SYSTEM_PROMPT = """You are a life-sciences CRM assistant helping a pharma field rep plan \
next steps after an HCP interaction. Given the interaction summary and history below, suggest 2-4 \
concrete, actionable follow-up items (e.g. scheduling a meeting, sending specific materials, adding \
to an event/advisory board invite list, escalating to medical affairs). Return ONLY a JSON array of \
short strings, no markdown fences, no commentary.
"""


def suggest_followups_llm(interaction_summary: str, history_summary: str) -> list:
    messages = [
        ("system", FOLLOWUP_SYSTEM_PROMPT),
        ("user", f"LATEST INTERACTION:\n{interaction_summary}\n\nHCP HISTORY:\n{history_summary or 'No prior interactions.'}"),
    ]
    response = invoke_with_fallback(messages, temperature=0.4)
    try:
        content = response.content.strip()
        content = re.sub(r"^```(json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            content = match.group(0)
        result = json.loads(content)
        return [str(item) for item in result][:4]
    except (json.JSONDecodeError, AttributeError):
        return []
