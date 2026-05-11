# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""
contracts/fact_checker.py

This is the REAL GenLayer Intelligent Contract version of the fact checker.
Deploy this on-chain once GenLayer mainnet is live.

On-chain, GenLayer validators will:
1. Each run this contract independently (non-deterministic: web access + LLM)
2. Compare results via Equivalence Principle
3. Reach consensus automatically

No FastAPI needed — the chain IS the consensus layer.
"""

from genlayer import *


class FactChecker(gl.Contract):
    # Persistent storage: claim history
    checks: TreeMap[str, str]   # claim_id -> verdict
    check_count: u64

    def __init__(self):
        self.checks = TreeMap[str, str]()
        self.check_count = u64(0)

    @gl.public.view
    def get_verdict(self, claim_id: str) -> str:
        """Read stored verdict for a previously checked claim."""
        return self.checks.get(claim_id, "NOT_FOUND")

    @gl.public.view
    def get_count(self) -> u64:
        return self.check_count

    @gl.public.write
    def check_claim(self, claim: str) -> None:
        """
        Non-deterministic method: each GenLayer validator runs this independently.
        - Fetches web data (non-deterministic)
        - Calls LLM (non-deterministic)
        - GenLayer's Equivalence Principle ensures consensus across validators
        """
        # Web access — GenLayer fetches from live web
        search_result = gl.get_webpage(
            f"https://www.google.com/search?q={claim.replace(' ', '+')}+fact+check",
            mode="text",
        )

        # LLM call — each validator's LLM may produce slightly different output
        # but must reach an "equivalent" result for consensus
        verdict_raw = gl.exec_prompt(
            f"""You are a fact checker. Analyze this claim: "{claim}"

Search context:
{search_result[:2000]}

Respond with ONLY one word: TRUE, FALSE, or UNVERIFIABLE.
"""
        )

        verdict = verdict_raw.strip().upper()
        if verdict not in ("TRUE", "FALSE", "UNVERIFIABLE"):
            verdict = "UNVERIFIABLE"

        # Store result on-chain
        claim_id = str(self.check_count)
        self.checks[claim_id] = f"{claim}||{verdict}"
        self.check_count = u64(int(self.check_count) + 1)
