import os
import json
import asyncio
import httpx
from dataclasses import dataclass
from typing import Literal
from agent.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from agent.search import search

Verdict = Literal["TRUE", "FALSE", "UNVERIFIABLE"]

PROVIDERS = [
    {"name": "groq/llama-3.3-70b-versatile", "url": "https://api.groq.com/openai/v1/chat/completions", "key_env": "GROQ_API_KEY", "model": "llama-3.3-70b-versatile"},
    {"name": "groq/llama-3.1-8b-instant", "url": "https://api.groq.com/openai/v1/chat/completions", "key_env": "GROQ_API_KEY", "model": "llama-3.1-8b-instant"},
    {"name": "glm/glm-4-flash", "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions", "key_env": "GLM_API_KEY", "model": "glm-4-flash"},
]

@dataclass
class NodeResult:
    node_id: int
    model: str
    verdict: Verdict
    confidence: float
    reasoning: str
    sources_used: list[str]
    raw_response: str

async def run_node(node_id, claim, search_context="", model=None):
    provider = PROVIDERS[node_id % len(PROVIDERS)]
    model_name = model or provider["name"]
    api_model = provider["model"]
    api_key = os.getenv(provider["key_env"], "")

    if not api_key:
        return NodeResult(node_id=node_id, model=model_name, verdict="UNVERIFIABLE",
            confidence=0.0, reasoning="Missing API key: " + provider["key_env"],
            sources_used=[], raw_response="")

    if not search_context:
        loop = asyncio.get_event_loop()
        search_context = await loop.run_in_executor(None, search, claim)
        print("[NODE " + str(node_id) + "] search chars: " + str(len(search_context)))

    prompt = USER_PROMPT_TEMPLATE.format(
        claim=claim,
        search_context=search_context or "No web search context available.")

    data = None
    for attempt in range(3):
        try:
            print("[NODE " + str(node_id) + "] attempt " + str(attempt+1) + " -> " + provider["name"])
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    provider["url"],
                    headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
                    json={"model": api_model,
                          "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                       {"role": "user", "content": prompt}],
                          "temperature": 0.2, "max_tokens": 512})
                response.raise_for_status()
                data = response.json()
                print("[NODE " + str(node_id) + "] success")
                break
        except (httpx.ReadError, httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt < 2:
                await asyncio.sleep(5)
            else:
                return NodeResult(node_id=node_id, model=model_name, verdict="UNVERIFIABLE",
                    confidence=0.0, reasoning="Connection error: " + type(e).__name__,
                    sources_used=[], raw_response="")
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 429:
                await asyncio.sleep(10 * (attempt+1))
                if attempt == 2:
                    return NodeResult(node_id=node_id, model=model_name, verdict="UNVERIFIABLE",
                        confidence=0.0, reasoning="Rate limited",
                        sources_used=[], raw_response="")
            else:
                return NodeResult(node_id=node_id, model=model_name, verdict="UNVERIFIABLE",
                    confidence=0.0, reasoning="HTTP error " + str(status),
                    sources_used=[], raw_response="")

    if data is None:
        return NodeResult(node_id=node_id, model=model_name, verdict="UNVERIFIABLE",
            confidence=0.0, reasoning="No response", sources_used=[], raw_response="")

    raw = data["choices"][0]["message"]["content"]
    parsed = _parse_verdict(raw)
    return NodeResult(node_id=node_id, model=model_name,
        verdict=parsed.get("verdict", "UNVERIFIABLE"),
        confidence=float(parsed.get("confidence", 0.5)),
        reasoning=parsed.get("reasoning", ""),
        sources_used=parsed.get("sources_used", []),
        raw_response=raw)

def _parse_verdict(raw):
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
    return {"verdict": "UNVERIFIABLE", "confidence": 0.0,
            "reasoning": "Failed to parse: " + raw[:200], "sources_used": []}
