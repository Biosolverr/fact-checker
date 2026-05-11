"""
agent/consensus.py

Implements GenLayer-style consensus (Optimistic Democracy / Equivalence Principle).

In GenLayer:
- Multiple validators run the same non-deterministic contract independently
- Results are compared; if majority agree → transaction is accepted
- If no consensus → appeal process (here simplified to UNVERIFIABLE)

We mirror this: N nodes vote, threshold fraction must agree.
"""

import asyncio
import os
from collections import Counter
from dataclasses import dataclass

from agent.node import NodeResult, Verdict, run_node


@dataclass
class ConsensusResult:
    claim: str
    final_verdict: Verdict
    confidence: float          # Average confidence of agreeing nodes
    vote_breakdown: dict       # {"TRUE": 2, "FALSE": 0, "UNVERIFIABLE": 1}
    consensus_reached: bool
    nodes: list[NodeResult]
    reasoning_summary: list[str]


async def run_consensus(
    claim: str,
    search_context: str = "",
    agent_count: int | None = None,
    threshold: float | None = None,
) -> ConsensusResult:
    """
    Run all validator nodes in parallel, then apply consensus logic.

    This mirrors GenLayer's validator network:
    - All nodes run independently (asyncio.gather = parallel execution)
    - Majority vote determines the outcome
    - Threshold must be met, otherwise UNVERIFIABLE
    """
    n = agent_count or int(os.getenv("AGENT_COUNT", "3"))
    thresh = threshold or float(os.getenv("CONSENSUS_THRESHOLD", "0.67"))

    # Run all nodes in parallel — like GenLayer validators executing concurrently
    tasks = [run_node(i, claim, search_context) for i in range(n)]
    nodes: list[NodeResult] = await asyncio.gather(*tasks, return_exceptions=False)

    return _apply_consensus(claim, nodes, thresh)


def _apply_consensus(
    claim: str,
    nodes: list[NodeResult],
    threshold: float,
) -> ConsensusResult:
    """
    Apply equivalence principle:
    - Count votes per verdict
    - If any verdict has >= threshold fraction of votes → consensus
    - Otherwise → UNVERIFIABLE (appeal would happen in real GenLayer)
    """
    votes = Counter(n.verdict for n in nodes)
    total = len(nodes)

    # Find if any verdict reaches threshold
    final_verdict: Verdict = "UNVERIFIABLE"
    consensus_reached = False

    # Sort by vote count descending
    for verdict, count in votes.most_common():
        if count / total >= threshold:
            final_verdict = verdict
            consensus_reached = True
            break

    # Compute average confidence of nodes that voted for the winner
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
        reasoning_summary=[f"Node {n.node_id} ({n.model}): {n.reasoning}" for n in nodes],
    )
