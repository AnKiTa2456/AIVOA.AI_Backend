"""Groq LLM wrapper with primary/fallback model support.

Primary model: gemma2-9b-it (fast, cheap — good for extraction/summarization).
Fallback model: llama-3.3-70b-versatile (used if the primary model errors out,
e.g. decommissioned or rate limited on Groq's side).
"""
from langchain_groq import ChatGroq

from app.config import settings


def _build(model_name: str, temperature: float = 0.2):
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=model_name,
        temperature=temperature,
    )


_primary = None
_fallback = None


def get_primary_llm(temperature: float = 0.2) -> ChatGroq:
    global _primary
    if _primary is None:
        _primary = _build(settings.groq_model, temperature)
    return _primary


def get_fallback_llm(temperature: float = 0.2) -> ChatGroq:
    global _fallback
    if _fallback is None:
        _fallback = _build(settings.groq_fallback_model, temperature)
    return _fallback


def invoke_with_fallback(messages, temperature: float = 0.2):
    """Invoke the primary Groq model, transparently retrying on the fallback
    model if the primary call raises (e.g. model deprecated/unavailable)."""
    try:
        return get_primary_llm(temperature).invoke(messages)
    except Exception:
        return get_fallback_llm(temperature).invoke(messages)


def get_chat_llm(temperature: float = 0.2) -> ChatGroq:
    """LLM instance used for the LangGraph agent's tool-calling loop."""
    return get_primary_llm(temperature)
