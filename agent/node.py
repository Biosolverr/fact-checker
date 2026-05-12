import os
import json
import asyncio
import httpx
from dataclasses import dataclass
from typing import Literal
from agent.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

Verdict = Literal["TRUE", "FALSE", "UNVERIFIABLE"]

PROVIDERS = [
    {
        "name": "groq/llama-3.3-70b-versatile",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_env": "GROQ_API_KEY",
        "model": "llama-3.3-70b-versatile",
    },
    {
        "name": "groq/llama-3.3-70b-versatile-2",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_env": "GROQ_API_KEY",
        "model": "llama-3.3-70b-versatile",
    },
    {
        "name": "glm/glm-4-flash",
        "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "key_env": "GLM_API_KEY",
        "model": "glm-4-flash",
    },
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
            confidence=0.0, reasoning=f"Missing API key: {provider['key_env']}",
            sources_used=[], raw_response="")

    prompt = USER_PROMPT_TEMPLATE.format(
        claim=claim,
        search_context=search_context or "No web search context available.")

    data = None
    last_error = "No response"

    for attempt in range(3):
        try:
            print(f"[NODE {node_id}] attempt {attempt+1} -> {provider['name']}")
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    provider["url"],
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": api_model,
                          "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                       {"role": "user", "content": prompt}],
                          "temperature": 0.2, "max_tokens": 512})
                response.raise_for_status()
                data = response.json()
                print(f"[NODE {node_id}] success")
                break

        except (httpx.ReadError, httpx.TimeoutException, httpx.ConnectError) as e:
            last_error = f"Connection error: {type(e).__name__}: {e}"
            print(f"[NODE {node_id}] ERROR attempt {attempt+1}: {last_error}")
            if attempt < 2:
                await asyncio.sleep(5)

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            body = e.response.text[:500]
            last_error = f"HTTP {status}: {body}"
            print(f"[NODE {node_id}] HTTP ERROR {status}: {body}")
            if status == 429:
                wait = 10 * (attempt + 1)
                print(f"[NODE {node_id}] Rate limited, waiting {wait}s...")
                await asyncio.sleep(wait)
            else:
                return NodeResult(node_id=node_id, model=model_name, verdict="UNVERIFIABLE",
                    confidence=0.0, reasoning=last_error,
                    sources_used=[], raw_response="")

        except Exception as e:
            last_error = f"Unexpected error: {type(e).__name__}: {e}"
            print(f"[NODE {node_id}] UNEXPECTED ERROR: {last_error}")
            if attempt < 2:
                await asyncio.sleep(3)

    if data is None:
        print(f"[NODE {node_id}] FAILED after 3 attempts: {last_error}")
        return NodeResult(node_id=node_id, model=model_name, verdict="UNVERIFIABLE",
            confidence=0.0, reasoning=last_error, sources_used=[], raw_response="")

    raw = data["choices"][0]["message"]["content"]
    print(f"[NODE {node_id}] raw response:\n{raw}\n---")
    parsed = _parse_verdict(raw)

    verdict = parsed.get("verdict", "UNVERIFIABLE")
    if verdict not in ("TRUE", "FALSE", "UNVERIFIABLE"):
        print(f"[NODE {node_id}] Invalid verdict '{verdict}', defaulting to UNVERIFIABLE")
        verdict = "UNVERIFIABLE"

    return NodeResult(node_id=node_id, model=model_name,
        verdict=verdict,
        confidence=float(parsed.get("confidence", 0.5)),
        reasoning=parsed.get("reasoning", ""),
        sources_used=parsed.get("sources_used", []),
        raw_response=raw)


def _parse_verdict(raw):
    text = raw.strip()

    # Strip markdown code fences: ```json ... ``` or ``` ... ```
    if text.startswith("```"):
        lines = text.splitlines()
        inner = [l for l in lines[1:] if l.strip() != "```"]
        text = "\n".join(inner).strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting the first JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    # Last resort: find verdict keyword in plain text
    upper = text.upper()
    verdict = "UNVERIFIABLE"
    for v in ("TRUE", "FALSE", "UNVERIFIABLE"):
        if v in upper:
            verdict = v
            break

    print(f"[PARSE] Could not parse JSON, extracted verdict='{verdict}' from text")
    return {
        "verdict": verdict,
        "confidence": 0.3,
        "reasoning": f"(auto-extracted from non-JSON response) {text[:300]}",
        "sources_used": [],
    }

