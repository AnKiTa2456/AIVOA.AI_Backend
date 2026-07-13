# AI-First HCP CRM — Backend

FastAPI + LangGraph + Groq backend for the "Log HCP Interaction" screen of an AI-first CRM
HCP module. Companion frontend repo: https://github.com/AnKiTa2456/AIVOA.AI_Frontend

## Table of Contents

1. [What this project is](#what-this-project-is)
2. [How it works — the flow](#how-it-works--the-flow)
3. [Technology used, and why](#technology-used-and-why)
4. [What's included](#whats-included)
5. [The LangGraph Agent](#the-langgraph-agent)
6. [The 6 tools](#the-6-tools-appagenttoolspy)
7. [Alternates & deviations from the brief](#alternates--deviations-from-the-brief)
8. [Running locally](#running-locally)
9. [Verifying everything actually works](#verifying-everything-actually-works)
10. [API Overview](#api-overview)
11. [Project Structure](#project-structure)
12. [Glossary](#glossary-for-newcomers-to-langgraph)

## What this project is

A pharma field rep needs to log every conversation they have with a Healthcare Professional
(HCP) — what was discussed, samples/brochures handed over, the HCP's reaction, and what to
do next. This backend gives them two ways to do that (a structured form, or just describing
it in plain English to a chat assistant), and both are powered by the **same** AI agent, so
the data ends up equally clean either way.

## How it works — the flow

Two entry points converge on the same place. Read top-to-bottom for the mental model:

```
 A) Structured form path                 B) Conversational path
 ────────────────────────                ─────────────────────
 React form filled in            User types free text, e.g.
        │                        "Met Dr. Sharma, discussed
        ▼                         OncoBoost Phase III data,
 POST /api/interactions            positive sentiment"
 (exact field values)                     │
        │                                 ▼
        │                        POST /api/chat {session_id, message}
        │                                 │
        │                                 ▼
        │                        LangGraph StateGraph.invoke()
        │                          ┌────────────────────────┐
        │                          │ agent node:              │
        │                          │  Groq LLM decides which  │
        │                          │  tool(s) to call, if any │
        │                          └───────────┬──────────────┘
        │                                      │ tool call requested
        │                                      ▼
        │                          ┌────────────────────────┐
        │                          │ tools node (ToolNode):   │
        │                          │  runs the chosen tool     │
        │                          └───────────┬──────────────┘
        │                                      │ tool result fed back
        │                                      ▼
        │                          agent node again → either calls
        │                          another tool, or writes a reply
        │                                      │
        ▼                                      ▼
 log_interaction() ◄───────────── same Python functions in tools.py ─────┐
 edit_interaction()                                                       │
 get_interaction_history()  ◄── both paths call these directly ──────────┤
 suggest_followups()                                                     │
 schedule_followup()                                                     │
 search_hcp()                                                            │
        │                                                                │
        ▼                                                                │
 SQLAlchemy ORM  →  PostgreSQL (hcps / interactions / follow_ups / chat_messages)
        │
        ▼
 JSON response  →  React updates Redux store  →  UI re-renders
```

Concretely, for one chat message like *"Met Dr. Sharma, discussed OncoBoost Phase III data,
positive sentiment, shared brochure"*:

1. Frontend sends `{session_id, message}` to `POST /api/chat`.
2. `run_agent()` (`app/agent/agent.py`) invokes the compiled LangGraph graph with that message,
   keyed to the session's conversation thread.
3. The `agent` node asks the Groq LLM, with all 6 tools available, "what should happen with
   this message?" The LLM replies with a **tool call**: `log_interaction(raw_text="Met Dr.
   Sharma...")`.
4. LangGraph routes control to the `tools` node, which actually executes `log_interaction`:
   - It calls the LLM *again*, but this time with a strict extraction prompt
     (`app/agent/extraction.py`) that turns the sentence into structured JSON — HCP name,
     topics, sentiment, materials shared, a one-line summary, etc.
   - It writes a new row into the `interactions` table (and `hcps` if the HCP is new).
5. The tool's JSON result is fed back to the `agent` node, which may decide to chain another
   tool (e.g. call `suggest_followups` next) or just reply in natural language.
6. The final reply, the list of tools that ran, and the created/updated interaction record are
   returned to the frontend as one JSON response.
7. The React chat panel shows the reply; the structured form on the same screen re-hydrates
   itself with the new interaction's fields, so both views stay in sync.

The structured-form path (A) skips steps 2–3 and calls `log_interaction()` / `edit_interaction()`
directly with exact field values instead of free text — no LLM entity-extraction needed there,
since the fields are already structured. Everything downstream (steps 4's DB write onward) is
identical code either way.

## Technology used, and why

| Layer | Choice | Why |
|---|---|---|
| AI agent framework | **LangGraph** | Required by the brief. Gives an explicit, inspectable graph (`agent` ⇄ `tools`) instead of a black-box "agent.run()" — useful both for reliability (you can see exactly which tool ran) and for explaining the system in the demo video. |
| LLM provider | **Groq** (`gemma2-9b-it` primary / `llama-3.3-70b-versatile` fallback) | Required by the brief. Groq's inference is very fast, which matters for a chat UI where the rep is waiting on a reply. |
| API framework | **FastAPI** | Async-friendly, automatic OpenAPI docs (`/docs`) for free, first-class Pydantic validation — makes the API self-documenting for graders. |
| ORM | **SQLAlchemy 2.0** | Database-agnostic: the exact same models work against Postgres or MySQL by changing one connection string, satisfying the brief's "MySQL/PostgreSQL" either/or. |
| Database | **PostgreSQL** (MySQL-compatible) | Relational integrity between HCPs → Interactions → FollowUps matters here (a follow-up must belong to a real interaction); a relational DB models that naturally. |
| LLM orchestration library | **LangChain Core** (via `langchain-groq`) | LangGraph is built on top of LangChain's message/tool primitives — needed for `@tool`, `bind_tools`, and message types. |

## What's included

- A LangGraph agent with **6 tools** (2 required + 4 more, see below) wired to a real Groq LLM.
- Automatic **LLM fallback**: if the configured Groq model is unavailable, every LLM call
  transparently retries on a second model — see [Alternates](#alternates--deviations-from-the-brief).
- Full CRUD for HCP interactions, backed by Postgres, reachable from both a REST API and the
  conversational agent.
- Per-session conversation memory (`MemorySaver` checkpointer) so the agent remembers what
  "that interaction" or "her" refers to across turns.
- Seed data (5 sample HCPs) created automatically on first startup.
- Auto-generated interactive API docs at `/docs` (Swagger UI) — you can call every endpoint,
  including the chat agent, straight from the browser with no frontend needed.

## The LangGraph Agent

The agent is a `StateGraph` with two nodes:

- **`agent`** — a Groq chat model bound to the 6 tools below via `.bind_tools()`. It reads the
  conversation and either calls a tool or answers the rep directly.
- **`tools`** — a `ToolNode` that executes whichever tool(s) the model asked for and feeds the
  results back to the `agent` node.

`START → agent → (tools_condition) → tools → agent → … → END`, checkpointed per chat
`session_id` via `MemorySaver`, so the agent remembers context across turns of one conversation
(this is what lets a rep say "change *that* interaction's sentiment" without repeating the ID).

Its role in the HCP module: it's the single orchestration layer between the rep's natural
language / form input and the CRM's data — extracting structured facts from unstructured text,
keeping records accurate as reps correct themselves mid-conversation, surfacing HCP history for
context, and proactively recommending next-best-actions.

### The 6 tools (`app/agent/tools.py`)

| # | Tool | Purpose |
|---|------|---------|
| 1 | **`log_interaction`** *(required)* | Creates a new interaction. If given `raw_text` (e.g. "Met Dr. Sharma, discussed OncoBoost Phase III data, positive sentiment, shared brochure"), it calls the Groq LLM (`app/agent/extraction.py`) to extract HCP name, interaction type, topics, sentiment, outcomes, follow-ups, materials/samples, and a one-line AI summary — then persists the record. Explicit structured fields (from the form) override extracted ones. |
| 2 | **`edit_interaction`** *(required)* | Modifies an already-logged interaction. Accepts a free-text `instruction` ("change sentiment to positive and add a follow-up to send samples") which the LLM converts into a partial JSON patch, and/or an explicit `updates` dict from the form. Applies the patch and returns the updated record. |
| 3 | **`get_interaction_history`** | Fetches the N most recent interactions logged for an HCP, giving the agent (and the rep) context before logging something new. |
| 4 | **`suggest_followups`** | Uses the LLM to generate 2–4 concrete next-best-actions from the latest interaction plus the HCP's history. |
| 5 | **`schedule_followup`** | Persists a concrete follow-up task/reminder tied to an interaction. |
| 6 | **`search_hcp`** | Autocomplete/search over known HCPs by name, specialty, or institution. |

## Alternates & deviations from the brief

Full transparency on where the running system differs from a literal reading of the brief, and
why — worth mentioning in the demo video rather than hiding:

| Brief says | What actually happened | Why / mitigation |
|---|---|---|
| Use Groq's `gemma2-9b-it` | **Groq has since decommissioned `gemma2-9b-it` server-side** (confirmed live: `groq.BadRequestError: model_decommissioned`). It's still configured as the primary model (`GROQ_MODEL` in `.env`), but every LLM call — in `app/agent/graph.py` (the agent's tool-calling node) and `app/agent/extraction.py` (entity extraction / follow-up suggestions) — is wrapped in a try/except that transparently retries on `llama-3.3-70b-versatile` if the primary call fails. So the app runs correctly today, entirely on the fallback model, with zero config changes needed. If Groq ships a replacement for `gemma2-9b-it`, just update `GROQ_MODEL` in `.env`. | This is outside the codebase's control — Groq's hosted model catalog changed after the brief was written. The brief itself anticipated this by naming `llama-3.3-70b-versatile` as a model "to consider for context." |
| Postgres/MySQL, implicitly via Docker (`docker-compose.yml` is provided) | Local development was done against a native Homebrew-installed Postgres (no Docker available on that machine), by creating the `hcp_user` role / `hcp_crm` database directly in it. `docker-compose.yml` is still included and works identically for anyone who does have Docker — same credentials, same port. | Functionally identical either way: it's real PostgreSQL, just not containerized on that particular dev machine. |
| — | `psycopg2-binary` is pinned to `2.9.10` rather than an older patch version. | `2.9.9`'s wheel doesn't build on Python 3.13 (a C-API incompatibility unrelated to this project) — `2.9.10` has a compatible prebuilt wheel. |

## Running locally

### 1. Database (PostgreSQL via Docker)

```bash
docker compose up -d
```

Starts Postgres on `localhost:5432` (db `hcp_crm`, user `hcp_user`, pass `hcp_pass`). Tables
are created automatically on backend startup — no manual migration needed.

> No Docker? Create the same role/db in any local Postgres install instead:
> `createuser hcp_user -P` (password `hcp_pass`) then `createdb hcp_crm -O hcp_user`.

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

## Verifying everything actually works

Three independent things to check — each proves a different part of the stack is real, not
mocked:

### 1. The API is up and the LangGraph tools respond

Open http://localhost:8000/docs (Swagger UI) and try any endpoint directly from the browser —
no frontend required. Or from a terminal:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/hcps                 # 5 seeded HCPs

# Exercise the full agent (log → edit → history → suggest → schedule → search)
curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d \
  '{"session_id":"demo","message":"Met Dr. Sharma, discussed OncoBoost Phase III data, positive sentiment, shared brochure"}'

curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d \
  '{"session_id":"demo","message":"Change the sentiment on that to Neutral"}'

curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d \
  '{"session_id":"demo","message":"What'"'"'s Dr. Sharma'"'"'s interaction history?"}'

curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d \
  '{"session_id":"demo","message":"Schedule a follow-up to send her the Phase III PDF by next Friday"}'

curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d \
  '{"session_id":"demo","message":"Which HCPs specialize in Oncology?"}'
```

Each response's `tool_calls` array names exactly which LangGraph tool(s) ran — that's your
proof the LLM is actually choosing and invoking tools, not just chatting.

### 2. The database is really being written to

Tables are created automatically on startup, and 5 sample HCPs are seeded. Connect with `psql`:

```bash
psql -h localhost -p 5432 -U hcp_user -d hcp_crm
# password: hcp_pass (or `export PGPASSWORD=hcp_pass` first to skip the prompt)
```

Useful queries once connected:

```sql
\dt                                                     -- list tables
SELECT name, specialty, institution FROM hcps;
SELECT id, hcp_id, interaction_type, sentiment, topics_discussed, source FROM interactions;
SELECT id, interaction_id, description, due_date, status FROM follow_ups;
SELECT session_id, role, content FROM chat_messages ORDER BY created_at;
\q
```

Or as one-liners without entering the `psql` shell:

```bash
psql -h localhost -U hcp_user -d hcp_crm -c "SELECT * FROM interactions;"
```

You should see rows appear after saving via the structured form, or after each `curl`/chat
command above — that's the proof the LangGraph tools are writing real data, not returning
canned text. A GUI client (TablePlus, Postico, DBeaver) works too — connect with host
`localhost`, port `5432`, user `hcp_user`, password `hcp_pass`, database `hcp_crm`.

> If you're running Postgres via `docker compose up -d` instead of a local install, the same
> credentials apply — Docker just runs the server in a container on the same port.

### 3. The LLM fallback is actually working

```bash
grep GROQ_MODEL .env        # should show gemma2-9b-it — the "requested" primary model
```

If you see a normal reply (not a 500 error) from the `curl`/chat commands above, the fallback
in `app/agent/graph.py` and `app/agent/extraction.py` already kicked in silently (since
`gemma2-9b-it` is decommissioned — see [Alternates](#alternates--deviations-from-the-brief)).
You can prove this by temporarily setting `GROQ_FALLBACK_MODEL` to an invalid name and
restarting — you'll then see the real error surface, confirming the try/except really is doing
something.

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

## Glossary (for newcomers to LangGraph)

- **Agent** — here, just "an LLM that can call functions (tools) instead of only returning
  text." It decides *which* tool to call and *with what arguments*, based on the conversation.
- **Tool** — a regular Python function (decorated with `@tool`) with a typed input schema, that
  the LLM can choose to invoke. The LLM never runs the function itself — it asks for it, and
  LangGraph's `ToolNode` actually executes it.
- **StateGraph** — LangGraph's core abstraction: a graph of nodes (plain functions) that all
  read and write a shared `state` object (here, a growing list of `messages`). Control flows
  from node to node along edges until it reaches `END`.
- **`tools_condition`** — a built-in LangGraph edge that inspects the agent's last message: if
  it contains a tool call, route to the `tools` node; otherwise route to `END`.
- **Checkpointer / `MemorySaver`** — persists the graph's `state` between calls, keyed by a
  `thread_id` (here, the chat `session_id`), so the agent has memory across turns of one
  conversation. (It's in-memory only — restarting the backend clears chat memory, though the
  underlying database rows are unaffected.)
- **Fallback model** — if calling the primary LLM raises an exception (rate limit, decommissioned
  model, network blip), the code catches it and retries the same request against a second,
  different model — see `invoke_with_fallback()` in `app/agent/llm.py`.
- **ORM (SQLAlchemy)** — lets Python code (`app/models.py`) describe database tables as classes,
  so the rest of the app reads/writes Python objects instead of writing raw SQL.
