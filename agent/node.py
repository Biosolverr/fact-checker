"""
agent/node.py

A single validator node. Mirrors a GenLayer validator that:
- Runs the contract non-deterministically (fetches web data + calls LLM)
- Returns a structured result to be compared in consensus
"""

import os
import json
import httpx
from dataclasses import dataclass
from typing import Literal

from agent.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Models available via OpenRouter — rotate across nodes for diversity
MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "z-ai/glm-4.5-air:free",
    "qwen/qwen3-coder:free",
]

Verdict = Literal["TRUE", "FALSE", "UNVERIFIABLE"]


@dataclass
class NodeResult:
    node_id: int
    model: str
    verdict: Verdict
    confidence: float
    reasoning: str
    sources_used: list[str]
    raw_response: str


async def run_node(
    node_id: int,
    claim: str,
    search_context: str = "",
    model: str | None = None,
) -> NodeResult:
    """
    Run a single validator node.
    Each node independently calls an LLM to evaluate the claim.
    This is equivalent to a GenLayer validator executing a contract.
    """
    selected_model = model or MODELS[node_id % len(MODELS)]
    prompt = USER_PROMPT_TEMPLATE.format(
        claim=claim,
        search_context=search_context or "No web search context available.",
    )

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in environment")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/fact-checker",
            },
            json={
                "model": selected_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,  # Low temp for factual tasks
                "max_tokens": 512,
            },
        )
       response.raise_for_status()
    data = response.json()
    print(f"[NODE {node_id}] raw response: {data}")

    raw = data["choices"][0]["message"]["content"]

    # Parse JSON response from the LLM
    parsed = _parse_verdict(raw)

    return NodeResult(
        node_id=node_id,
        model=selected_model,
        verdict=parsed.get("verdict", "UNVERIFIABLE"),
        confidence=float(parsed.get("confidence", 0.5)),
        reasoning=parsed.get("reasoning", ""),
        sources_used=parsed.get("sources_used", []),
        raw_response=raw,
    )


def _parse_verdict(raw: str) -> dict:
    """Extract JSON from LLM response, even if it has extra text around it."""
    raw = raw.strip()
    # Try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Try to find JSON block
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass
    # Fallback
    return {
        "verdict": "UNVERIFIABLE",
        "confidence": 0.0,
        "reasoning": f"Failed to parse response: {raw[:200]}",
        "sources_used": [],
    }
