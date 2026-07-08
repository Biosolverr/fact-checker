# 🔍 Decentralized Fact Checker — GenLayer (Studionet)

A static frontend that talks **directly** to an intelligent contract on
GenLayer Studionet. No backend — every call (`check_claim`, `get_verdict`,
`get_count`) goes through `genlayer-js` straight from the browser to the
network's validators.

## How it works

Browser (index.html)
│  genlayer-js: writeContract / readContract
▼
GenLayer Studionet
│  gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
▼
Network validators (leader + consensus) → gl.nondet.exec_prompt(...)
│
▼
checks[claim_id] = "claim||VERDICT"  (on-chain, TreeMap)

`contracts/fact_checker.py` is what's deployed on Studionet. The leader
node calls `gl.nondet.exec_prompt`, the other validators confirm the
response format (`validator_fn`) — that's GenLayer's consensus happening
entirely on the network side, not in the browser or on a backend.

## Project structure

fact-checker/
├── index.html            # entire frontend (genlayer-js, importmap, no build step)
├── contracts/
│   ├── fact_checker.py   # intelligent contract (deployed on Studionet)
│   └── tests_proof.json  # proof of successful test transactions
├── vercel.json           # static hosting + SPA fallback
└── .gitignore

Files unrelated to this architecture have been removed (the old FastAPI
backend `api/`, `agent/`, `Dockerfile`, `Procfile`, `requirements.txt`,
`.env.example`) — they implemented a parallel setup with direct
Groq/GLM/Serper calls from the server/browser, which is no longer needed
now that the contract itself talks to the validators.

## Deploying to Vercel

```bash
npm i -g vercel   # if not installed yet
vercel             # from the project root, static site, no build step
```

Or via the Vercel dashboard: New Project → Import repo →
Framework Preset: **Other** → Build Command: (empty) → Output Directory: `.`

## Contract

The contract address and the demo account's private key are hardcoded
directly in `index.html` (the `CONTRACT` and `PRIVATE_KEY` constants). For
production you should:
- generate a new key and avoid hardcoding it in a public frontend
  (or use a wallet connection instead of `createAccount`),
- deploy your own instance of `fact_checker.py` via GenLayer Studio and
  set its address as `CONTRACT`.
