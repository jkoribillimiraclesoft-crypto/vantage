"""Enrich raw items with AI-generated analysis, scored against the user's profile.

Design choice: the model is only ever asked to produce ANALYSIS fields
(summary, why it matters, why learn it, scores, tier, category, gcp_use).
It never generates title/url/source/date — those are passed through
unchanged from the real fetched item, so nothing about "what happened and
where it came from" is ever hallucinated, only the interpretation of it.
"""

import json
import os

import anthropic

MODEL = "claude-sonnet-4-6"
BATCH_SIZE = 8

SCHEMA_INSTRUCTIONS = """For EACH item, return an object with exactly these fields:
{
  "index": <the item's index as given>,
  "tier": <1, 2, 3, or 4 — 1 = directly GCP/BigQuery/VertexAI/DataEngineering critical,
           2 = AI agents/RAG/MCP/LLM apps/data+AI, 3 = broader dev ecosystem (open models,
           LangGraph, MLOps, AI infra), 4 = general AI news with little data-engineering relevance>,
  "category": "<short category label, e.g. 'BigQuery', 'AI Agents', 'MCP', 'Data Quality + AI'>",
  "summary": "<3-5 sentence neutral summary of the actual content>",
  "whats_new": "<what specifically changed or was introduced>",
  "why_matters": "<practical importance and impact, grounded in the content, not generic>",
  "why_learn": "<personalized explanation connecting this SPECIFICALLY to GCP + Data Engineering + AI
                for this user's profile. Never generic like 'AI is growing fast'. If it has no real
                data-engineering angle, say so honestly rather than inventing a connection.>",
  "what_to_learn": ["<specific skill/technology 1>", "<...>"],
  "gcp_use": "Yes" | "Potentially" | "No",
  "gcp_use_case": "<if Yes/Potentially, one concrete GCP data-engineering use case; if No, say why not>",
  "is_gcp": true | false,
  "is_de": true | false,
  "scores": {
    "gcp": <0-100 GCP relevance>,
    "de": <0-100 Data Engineering relevance>,
    "ai": <0-100 general AI relevance>,
    "career": <0-100 career impact for this profile>,
    "adoption": <0-100 current industry adoption>,
    "future": <0-100 future potential>
  }
}
Be honest and specific — if an item genuinely has low GCP/data-engineering relevance, score it low
rather than inflating relevance to seem more useful. Return ONLY a JSON array of these objects,
no markdown fences, no commentary before or after."""


def get_api_key():
    """Checks the environment first, then Streamlit secrets (if running under Streamlit)."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return None


def _client():
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=api_key)


def _chunk(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def enrich_batch(raw_items, profile):
    """raw_items: list of dicts with title, url, source, published, raw_summary.
    Returns (enriched_items, errors) where enriched_items merge the analysis
    fields back onto the original raw metadata."""
    if not raw_items:
        return [], []

    client = _client()
    enriched = []
    errors = []

    for chunk in _chunk(raw_items, BATCH_SIZE):
        payload = [dict(index=i, title=it["title"], source=it["source"],
                         published=it["published"], raw_summary=it["raw_summary"])
                   for i, it in enumerate(chunk)]
        prompt = f"""You are a personal AI Career Intelligence Assistant and GCP Data Engineering Advisor.
Analyze each raw item below for this specific user profile:

Role: {profile['role']}
Primary expertise: {profile['expertise']}
AI experience: {profile['ai_experience']}

RAW ITEMS:
{json.dumps(payload)}

{SCHEMA_INSTRUCTIONS}"""
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in response.content if hasattr(b, "text")).strip()
            text = text.strip("` \n")
            if text.lower().startswith("json"):
                text = text[4:].strip()
            analyses = json.loads(text)
            for analysis in analyses:
                idx = analysis.get("index")
                if idx is None or idx >= len(chunk):
                    continue
                raw = chunk[idx]
                merged = dict(
                    title=raw["title"], source=raw["source"], source_url=raw["url"],
                    date=raw["published"],
                    tier=analysis.get("tier", 3),
                    category=analysis.get("category", "AI"),
                    is_gcp=bool(analysis.get("is_gcp", False)),
                    is_de=bool(analysis.get("is_de", False)),
                    summary=analysis.get("summary", ""),
                    whats_new=analysis.get("whats_new", ""),
                    why_matters=analysis.get("why_matters", ""),
                    why_learn=analysis.get("why_learn", ""),
                    what_to_learn=analysis.get("what_to_learn", []),
                    gcp_use=analysis.get("gcp_use", "No"),
                    gcp_use_case=analysis.get("gcp_use_case", ""),
                    scores=analysis.get("scores", {"gcp": 0, "de": 0, "ai": 0, "career": 0, "adoption": 0, "future": 0}),
                )
                enriched.append(merged)
        except Exception as e:
            errors.append(f"Enrichment batch failed ({len(chunk)} items): {e}")

    return enriched, errors
