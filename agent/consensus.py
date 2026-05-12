"""
agent/consensus.py

GenLayer-style consensus: Optimistic Democracy / Equivalence Principle.
Nodes run in parallel. Web search context is fetched once and shared with all nodes.
"""

import asyncio
import os
from collections import Counter
from dataclasses import dataclass

from agent.node import NodeResult, Verdict, run_node
from agent.search import search


@dataclass
class ConsensusResult:
    claim: str
    final_verdict: Verdict
    confidence: float
    vote_breakdown: dict
    consensus_reached: bool
    nodes: list[NodeResult]
    reasoning_summary: list[str]
    search_context: str


async def run_consensus(
    claim: str,
    search_context: str = "",
    agent_count: int | None = None,
    threshold: float | None = None,
) -> ConsensusResult:
    n = agent_count or int(os.getenv("AGENT_COUNT", "3"))
    thresh = threshold or float(os.getenv("CONSENSUS_THRESHOLD", "0.66"))

    # Fetch web search context if not provided
    if not search_context:
        print(f"[SEARCH] Searching for: {claim[:60]}")
        search_context = await asyncio.to_thread(search, claim)
        if search_context:
            print(f"[SEARCH] Got {len(search_context)} chars of context")
        else:
            print("[SEARCH] No results, proceeding without context")

    print(f"[CONSENSUS] Starting {n} nodes for claim: {claim[:60]}")

    tasks = [run_node(i, claim, search_context) for i in range(n)]
    nodes: list[NodeResult] = await asyncio.gather(*tasks)

    print(f"[CONSENSUS] All nodes done: {[n.verdict for n in nodes]}")

    result = _apply_consensus(claim, nodes, thresh)
    result.search_context = search_context
    return result


def _apply_consensus(
    claim: str,
    nodes: list[NodeResult],
    threshold: float,
) -> ConsensusResult:
    votes = Counter(n.verdict for n in nodes)
    total = len(nodes)

    final_verdict: Verdict = "UNVERIFIABLE"
    consensus_reached = False

    for verdict, count in votes.most_common():
        if count / total >= threshold:
            final_verdict = verdict
            consensus_reached = True
            break

    agreeing_nodes = [n for n in nodes if n.verdict == final_verdict]
    avg_confidence = (
        sum(n.confidence for n in agreeing_nodes) / len(agreeing_nodes)
        if agreeing_nodes else 0.0
    )

    return ConsensusResult(
        claim=claim,
        final_verdict=final_verdict,
        confidence=round(avg_confidence, 3),
        vote_breakdown=dict(votes),
        consensus_reached=consensus_reached,
        nodes=nodes,
        reasoning_summary=[
            f"Node {n.node_id} ({n.model}): {n.reasoning}" for n in nodes
        ],
        search_context="",
    )
