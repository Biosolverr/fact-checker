# 🔍 Decentralized Fact Checker

A GenLayer-like AI consensus system that fact-checks any claim using multiple independent LLM validator nodes.

## Architecture

Two parallel worlds exist in this repo:

### World 1 — FastAPI + Real LLMs (working system)

```
User Claim
    ↓
FastAPI /check endpoint
    ↓  ↓  ↓
3 Independent Validator Nodes (parallel)
├── Node 0: Groq llama-3.3-70b-versatile + Serper web search
├── Node 1: Groq llama-3.1-8b-instant    + Serper web search
└── Node 2: GLM-4-flash                  + Serper web search
    ↓
Consensus Logic (supermajority ≥ 66%)
    ↓
Verdict: TRUE / FALSE / UNVERIFIABLE
    ↓
HTML Frontend (direct Claude API calls from browser)
```

Each node independently searches the web via Serper.dev and reasons about the claim. Consensus is reached when ≥ 2/3 nodes agree. This mirrors GenLayer's Optimistic Democracy and Equivalence Principle.

### World 2 — GenLayer Intelligent Contract (on-chain proof of concept)

`contracts/fact_checker.py` implements the same logic as a real GenLayer contract using `gl.vm.run_nondet_unsafe` with explicit `leader_fn` / `validator_fn` separation:

- **leader_fn** — calls `gl.nondet.exec_prompt` to produce a verdict
- **validator_fn** — confirms the result is one of `TRUE / FALSE / UNVERIFIABLE`
- Results stored on-chain: `checks[claim_id] = "claim||verdict"`

Successfully tested on GenLayer testnet — 3/3 transactions finalized with multi-validator consensus. See `test_proof.json`.

## Project Structure

```
fact-checker/
├── agent/
│   ├── node.py           # Single validator node (LLM call + Serper web search)
│   ├── consensus.py      # Voting + equivalence logic
│   └── prompts.py        # System prompts
├── api/
│   └── main.py           # FastAPI app — serves /check and frontend
├── contracts/
│   └── fact_checker.py   # GenLayer Intelligent Contract (reference impl)
├── frontend/
│   └── index.html        # UI — 3 independent Claude API calls from browser
├── .env.example
├── requirements.txt
└── README.md
```

## Contract Interface

The frontend mirrors the contract's public methods exactly:

| Contract method | Frontend |
|---|---|
| `check_claim(claim)` | Run tab — calls 3 nodes in parallel, stores result |
| `get_verdict(claim_id)` | Get Verdict tab — lookup by ID |
| `get_count()` | Counter in header |
| `checks[id] = "claim\|\|verdict"` | localStorage — same format |

## Quickstart

```bash
# 1. Clone & install
git clone https://github.com/yourname/fact-checker
cd fact-checker
pip install -r requirements.txt

# 2. Set env vars
cp .env.example .env
# Fill in: GROQ_API_KEY, GLM_API_KEY, SERPER_API_KEY

# 3. Run
uvicorn api.main:app --reload
```

Then open the app and enter your Anthropic API key in the UI — the frontend calls Claude directly from the browser for the 3 validator nodes.

## Environment Variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key (llama-3.3-70b + llama-3.1-8b) |
| `GLM_API_KEY` | ZhipuAI API key (GLM-4-flash) |
| `SERPER_API_KEY` | Serper.dev key for web search (2500 free req/month) |
| `AGENT_COUNT` | Number of validator nodes (default: 3) |
| `CONSENSUS_THRESHOLD` | Fraction needed for consensus (default: 0.66) |

## GenLayer Contract

`contracts/fact_checker.py` is deployable on GenLayer testnet today and on mainnet once live.

Key design decisions:
- No web search in contract — LLM uses its own knowledge via `exec_prompt`
- `validator_fn` checks format only (is result a valid verdict?) — deterministic validation of a non-deterministic result
- Storage: `TreeMap[str, str]` with `"claim||verdict"` format
- Counter: `check_count: u64` increments on every write
