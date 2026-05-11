"""
api/main.py

FastAPI app exposing the fact-checker consensus system.
"""

import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.consensus import run_consensus, ConsensusResult

app = FastAPI(
    title="Decentralized Fact Checker",
    description="GenLayer-like multi-LLM consensus fact-checking agent",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Request / Response Models ----------

class CheckRequest(BaseModel):
    claim: str = Field(..., min_length=5, max_length=1000, description="Claim to fact-check")
    search_context: str = Field(default="", description="Optional web search context to pass to nodes")
    agent_count: int = Field(default=3, ge=1, le=7, description="Number of validator nodes")
    threshold: float = Field(default=0.67, ge=0.5, le=1.0, description="Consensus threshold (fraction)")


class NodeResultOut(BaseModel):
    node_id: int
    model: str
    verdict: str
    confidence: float
    reasoning: str
    sources_used: list[str]


class CheckResponse(BaseModel):
    claim: str
    final_verdict: str
    confidence: float
    consensus_reached: bool
    vote_breakdown: dict[str, int]
    nodes: list[NodeResultOut]
    reasoning_summary: list[str]


# ---------- Routes ----------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/check", response_model=CheckResponse)
async def check_claim(req: CheckRequest):
    """
    Submit a claim. N agent nodes independently evaluate it.
    Consensus logic determines the final verdict.

    This mirrors GenLayer's validator execution model:
    - Each node = one validator running the contract
    - Consensus = Optimistic Democracy / Equivalence Principle
    """
    try:
        result: ConsensusResult = await run_consensus(
            claim=req.claim,
            search_context=req.search_context,
            agent_count=req.agent_count,
            threshold=req.threshold,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    return CheckResponse(
        claim=result.claim,
        final_verdict=result.final_verdict,
        confidence=result.confidence,
        consensus_reached=result.consensus_reached,
        vote_breakdown=result.vote_breakdown,
        nodes=[
            NodeResultOut(
                node_id=n.node_id,
                model=n.model,
                verdict=n.verdict,
                confidence=n.confidence,
                reasoning=n.reasoning,
                sources_used=n.sources_used,
            )
            for n in result.nodes
        ],
        reasoning_summary=result.reasoning_summary,
    )
