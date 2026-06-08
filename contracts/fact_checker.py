# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *

class FactChecker(gl.Contract):
    checks: TreeMap[str, str]
    check_count: u64

    def __init__(self):
        self.checks = TreeMap[str, str]()
        self.check_count = u64(0)

    @gl.public.view
    def get_verdict(self, claim_id: str) -> str:
        return self.checks.get(claim_id, "NOT_FOUND")

    @gl.public.view
    def get_count(self) -> u64:
        return self.check_count

    @gl.public.write
    def check_claim(self, claim: str) -> None:
        def leader_fn():
            response = gl.nondet.exec_prompt(
                f"""You are a fact checker with broad world knowledge.
Analyze the following claim: "{claim}"

Respond with ONLY one word: TRUE, FALSE, or UNVERIFIABLE.
No explanation, no punctuation, just one word.""",
                response_format="json"
            )
            if isinstance(response, dict):
                v = str(list(response.values())[0]).strip().upper()
            else:
                v = str(response).strip().upper()
            if v not in ("TRUE", "FALSE", "UNVERIFIABLE"):
                v = "UNVERIFIABLE"
            return v

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            return leader_result.calldata in ("TRUE", "FALSE", "UNVERIFIABLE")

        verdict = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        claim_id = str(self.check_count)
        self.checks[claim_id] = f"{claim}||{verdict}"
        self.check_count = u64(int(self.check_count) + 1)
