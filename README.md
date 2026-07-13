# AI-First HCP CRM — Backend

FastAPI + LangGraph + Groq backend for the "Log HCP Interaction" screen of an AI-first CRM
HCP module. Companion frontend repo: https://github.com/AnKiTa2456/AIVOA.AI_Frontend

## Architecture

```
FastAPI
 ├─ /api/chat          → LangGraph agent turn (Groq LLM ⇄ tools)
 ├─ /api/interactions  → CRUD (structured form; routes through the same tools)
 └─ /api/hcps          → HCP search/autocomplete
        │
        ▼
 LangGraph StateGraph:  agent (Groq LLM) ⇄ ToolNode
        │
        ▼  6 tools
 log_interaction · edit_interaction · get_interaction_history
 suggest_followups · schedule_followup · search_hcp
        │
        ▼
 PostgreSQL / MySQL (SQLAlchemy)
```

## LangGraph Agent

The agent is a `StateGraph` with two nodes:

- **`agent`** — a Groq chat model (`gemma2-9b-it`, primary) bound to the 6 tools below. It
  reads the conversation and either calls a tool or answers the rep directly.
- **`tools`** — a `ToolNode` that executes whichever tool(s) the model asked for and feeds
  the results back to the `agent` node.

`START → agent → (tools_condition) → tools → agent → … → END`, checkpointed per chat
`session_id` via `MemorySaver`, so the agent remembers context across turns of one
conversation.

Its role in the HCP module: it's the single orchestration layer between the rep's natural
language / form input and the CRM's data — extracting structured facts from unstructured
text, keeping records accurate as reps correct themselves mid-conversation, surfacing HCP
history for context, and proactively recommending next-best-actions.

### The 6 tools (`app/agent/tools.py`)

| # | Tool | Purpose |
|---|------|---------|
| 1 | **`log_interaction`** | Creates a new interaction. If given `raw_text` (e.g. "Met Dr. Sharma, discussed OncoBoost Phase III data, positive sentiment, shared brochure"), it calls the Groq LLM (`app/agent/extraction.py`) to extract HCP name, interaction type, topics, sentiment, outcomes, follow-ups, materials/samples, and a one-line AI summary — then persists the record. Explicit structured fields (from the form) override extracted ones. |
| 2 | **`edit_interaction`** | Modifies an already-logged interaction. Accepts a free-text `instruction` ("change sentiment to positive and add a follow-up to send samples") which the LLM converts into a partial JSON patch, and/or an explicit `updates` dict from the form. Applies the patch and returns the updated record. |
| 3 | **`get_interaction_history`** | Fetches the N most recent interactions logged for an HCP, giving the agent (and the rep) context before logging something new. |
| 4 | **`suggest_followups`** | Uses the LLM to generate 2–4 concrete next-best-actions from the latest interaction plus the HCP's history. |
| 5 | **`schedule_followup`** | Persists a concrete follow-up task/reminder tied to an interaction. |
| 6 | **`search_hcp`** | Autocomplete/search over known HCPs by name, specialty, or institution. |

## Tech Stack

- Python, FastAPI, SQLAlchemy
- LangGraph (AI agent framework)
- Groq LLMs: `gemma2-9b-it` (primary), `llama-3.3-70b-versatile` (automatic fallback)
- PostgreSQL (MySQL also supported via `DATABASE_URL`)

## Running locally

### 1. Database (PostgreSQL via Docker)

```bash
docker compose up -d
```

Starts Postgres on `localhost:5432` (db `hcp_crm`, user `hcp_user`, pass `hcp_pass`). Tables
are created automatically on backend startup — no manual migration needed.

> Using MySQL instead? Set `DATABASE_URL=mysql+pymysql://user:pass@host:3306/hcp_crm` and
> `pip install pymysql`.

### 2. Backend

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set GROQ_API_KEY (create one at https://console.groq.com/keys)

uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## API Overview

| Method | Path | Description |
|---|---|---|
| POST | `/api/chat` | One turn of the LangGraph agent (`{session_id, message}` → `{reply, tool_calls, interaction}`) |
| GET | `/api/chat/{session_id}/history` | Persisted chat history for a session |
| POST | `/api/interactions` | Create an interaction (`log_interaction` tool) |
| GET | `/api/interactions?hcp_name=` | List/search interaction history |
| PUT | `/api/interactions/{id}` | Update an interaction (`edit_interaction` tool) |
| GET | `/api/interactions/{id}/followup-suggestions` | AI-suggested follow-ups (`suggest_followups` tool) |
| POST | `/api/interactions/{id}/followups` | Schedule a follow-up (`schedule_followup` tool) |
| GET | `/api/hcps?q=` | Search/autocomplete HCPs (`search_hcp` tool) |

## Project Structure

```
app/
  agent/
    llm.py          Groq LLM (primary + fallback)
    extraction.py   LLM prompts for entity extraction, edit patches, follow-up suggestions
    tools.py         The 6 LangGraph tools
    graph.py         StateGraph wiring (agent node + ToolNode)
    agent.py          run_agent() — single entry point used by the chat router
  routers/            chat.py · interactions.py · hcps.py
  models.py           SQLAlchemy models: HCP, Interaction, FollowUp, ChatMessage
  schemas.py           Pydantic request/response schemas
  crud.py               DB access layer shared by tools and routers
  main.py                FastAPI app, CORS, startup (create tables + seed HCPs)
docker-compose.yml     PostgreSQL for local dev
```
