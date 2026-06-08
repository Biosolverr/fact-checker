Repository Architecture

The project consists of two parallel worlds:
World 1 — FastAPI + real LLMs (agent/ + api/)
This is the working system right now. Three LLM nodes (Groq llama 70b, 
Groq llama 8b, GLM-4-flash) run in parallel, each searching via Serper.dev and casting a vote. 
Consensus is calculated using a majority threshold (66%). These are the "three API keys" you saw in the config.

World 2 — GenLayer contract (contracts/fact_checker.py)
This is a proof-of-concept demonstrating how the same logic runs on-chain. 
The contract uses the GenLayer SDK (gl.nondet.exec_prompt via gl.vm.run_nondet_unsafe) 
and has been successfully tested on the GenLayer testnet — 3/3 transactions finalized with 
consensus across multiple validator nodes. See test_proof.json for full test results.


# 🔍 Decentralized Fact Checker

A **GenLayer-like** AI agent system that uses multi-LLM consensus to fact-check any claim in real time.

## Architecture

```
User Claim
    ↓
OpenRouter (Gemini / GPT-4o / Claude)
    ↓  ↓  ↓
3 Independent Agent Nodes (Python)
    ↓
Equivalence / Consensus Logic
    ↓
FastAPI REST API
    ↓
HTML Frontend
```

Each agent independently searches the web and reasons about the claim.  
Consensus is reached when ≥ 2/3 agents agree on: `TRUE` / `FALSE` / `UNVERIFIABLE`.

This mirrors GenLayer's **Optimistic Democracy** and **Equivalence Principle** — where multiple validators run the same non-deterministic contract and must reach agreement.

## Quickstart

```bash
# 1. Clone & install
git clone https://github.com/yourname/fact-checker
cd fact-checker
pip install -r requirements.txt

# 2. Set env vars
cp .env.example .env
# Add your OPENROUTER_API_KEY

# 3. Run
uvicorn api.main:app --reload

# 4. Open frontend
open frontend/index.html
```

## Project Structure

```
fact-checker/
├── agent/
│   ├── node.py          # Single agent node (LLM call + web search)
│   ├── consensus.py     # Equivalence / voting logic
│   └── prompts.py       # System prompts
├── api/
│   └── main.py          # FastAPI app
├── contracts/
│   └── fact_checker.py  # GenLayer Intelligent Contract (reference impl)
├── frontend/
│   └── index.html       # UI
├── .env.example
├── requirements.txt
└── README.md
```

## GenLayer Contract

`contracts/fact_checker.py` shows how this would look as a **real** GenLayer Intelligent Contract — deployable on-chain once GenLayer mainnet launches.

## Environment Variables

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | Your OpenRouter API key |
| `AGENT_COUNT` | Number of validator nodes (default: 3) |
| `CONSENSUS_THRESHOLD` | Fraction needed to agree (default: 0.67) |
