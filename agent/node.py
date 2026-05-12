
"""
agent/node.py
"""

import os
import json
import asyncio
import httpx
from dataclasses import dataclass
from typing import Literal

from agent.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "z-ai/glm-4.5-air:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
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
    selected_model = model or MODELS[node_id % len(MODELS)]
    prompt = USER_PROMPT_TEMPLATE.format(
        claim=claim,
        search_context=search_context or "No web search context available.",
    )

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in environment")

    # Stagger nodes to avoid rate limits
    await asyncio.sleep(node_id * 3)

    data = None
    for attempt in range(3):
        try:
            print(f"[NODE {node_id}] attempt {attempt + 1} with {selected_model}")
            async with httpx.AsyncClient(timeout=60.0) as client:
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
                        "temperature": 0.2,
                        "max_tokens": 512,
                    },
                )
                response.raise_for_status()
                data = response.json()
                print(f"[NODE {node_id}] success")
                break

        except (httpx.ReadError, httpx.TimeoutException, httpx.ConnectError) as e:
            print(f"[NODE {node_id}] connection error attempt {attempt + 1}: {e}")
            if attempt < 2:
                await asyncio.sleep(8)
            else:
                return NodeResult(
                    node_id=node_id, model=selected_model,
                    verdict="UNVERIFIABLE", confidence=0.0,
                    reasoning=f"Connection error: {type(e).__name__}",
                    sources_used=[], raw_response="",
                )

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            print(f"[NODE {node_id}] HTTP {status} attempt {attempt + 1}")
            if status == 429:
                wait = 15 * (attempt + 1)
                print(f"[NODE {node_id}] rate limit, waiting {wait}s...")
                await asyncio.sleep(wait)
                if attempt == 2:
                    return NodeResult(
                        node_id=node_id, model=selected_model,
                        verdict="UNVERIFIABLE", confidence=0.0,
                        reasoning="Rate limited after 3 attempts",
                        sources_used=[], raw_response="",
                    )
            else:
                return NodeResult(
                    node_id=node_id, model=selected_model,
                    verdict="UNVERIFIABLE", confidence=0.0,
                    reasoning=f"HTTP error {status}",
                    sources_used=[], raw_response="",
                )

    if data is None:
        return NodeResult(
            node_id=node_id, model=selected_model,
            verdict="UNVERIFIABLE", confidence=0.0,
            reasoning="No response received",
            sources_used=[], raw_response="",
        )

    raw = data["choices"][0]["message"]["content"]
    print(f"[NODE {node_id}] raw: {raw[:200]}")
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
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass
    return {
        "verdict": "UNVERIFIABLE",
        "confidence": 0.0,
        "reasoning": f"Failed to parse: {raw[:200]}",
        "sources_used": [],
    }
