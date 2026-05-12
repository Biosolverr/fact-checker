"""
agent/search.py

Web search via Serper.dev API — 2500 free requests/month.
Requires SERPER_API_KEY in .env
"""

import os
import httpx


def search(query: str, max_results: int = 5) -> str:
    """
    Search via Serper.dev and return a formatted string with results.
    Returns empty string if search fails.
    """
    api_key = os.getenv("SERPER_API_KEY", "")
    if not api_key:
        print("[SEARCH] Missing SERPER_API_KEY")
        return ""

    try:
        response = httpx.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": api_key,
                "Content-Type": "application/json",
            },
            json={"q": query, "num": max_results},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        lines = []

        # Organic results
        for i, r in enumerate(data.get("organic", [])[:max_results], 1):
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            link = r.get("link", "")
            lines.append(f"[{i}] {title}\n{snippet}\nSource: {link}")

        # Knowledge graph if available
        kg = data.get("knowledgeGraph", {})
        if kg:
            desc = kg.get("description", "")
            if desc:
                lines.insert(0, f"[Knowledge Graph] {kg.get('title', '')}: {desc}")

        result = "\n\n".join(lines)
        return result

    except Exception as e:
        print(f"[SEARCH] Error: {e}")
        return ""
