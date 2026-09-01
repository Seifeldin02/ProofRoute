# Repository Project State

## Current phase

- Active spec: `proof-route`
- Workflow: requirements-first feature
- Status: requirements exist; MVP design completed; implementation/tasks phase has **not** started.
- Authoritative artifacts: `.kiro/specs/proof-route/requirements.md`, `.kiro/specs/proof-route/design.md`, `.kiro/specs/proof-route/.config.kiro`.
- No application or infrastructure code was changed during this design phase.

## Repository baseline

- `agent/my_agent.py`: sole AgentCore `@app.entrypoint`, Strands agent, normal `MemoryHook`, Mantle model routing, KB/web tools, and `NotifyOnlyGuardrailsHook`.
- `chatapp/app/main.py`: FastAPI app/router registration and authenticated `/chat` page.
- `chatapp/app/auth/middleware.py`: Cognito/dev-mode protection for every route not explicitly public; `/proof` will be protected automatically.
- `chatapp/app/agentcore/client.py`: existing Runtime streaming invocation and typed SSE parsing.
- `chatapp/app/agentcore/memory.py`: existing AgentCore Memory event retrieval.
- `chatapp/app/templates/base.html` and `templates/components/header.html`: reusable htmx/Tailwind/theme shell.
- `chatapp/requirements.txt`: pytest, pytest-asyncio, and Hypothesis are already available.
- CDK already provides Cognito, Runtime, Memory, KB, Guardrails, app deployment, CloudWatch/OpenTelemetry. No new AWS resources are permitted for ProofRoute MVP.

## Approved MVP direction

Deliver one closed loop in about 2.5 hours: pasted CV → deterministic canonical skills → deterministic readiness/jobs/gap → one fixed Automated Testing challenge → AST-constrained deterministic hidden-mutant evaluation → pass-gated skill promotion → before/after score and matches → compact progression snapshot.

Non-negotiable invariants:

- LLM output never determines extraction, score, gap, job matches, challenge contract, pass/fail, or promotion.
- One local `riyadh_jobs.json` dataset is authoritative; KB ingestion/retrieval is not in the numeric path.
- One existing agent entrypoint remains. Requirement 11 is reduced to a versioned state-action branch, not a second agent.
- Progress stores only target role, canonical skills, latest fixed challenge outcome, score, match count, and timestamp.
- Code evaluation is demo-only containment, not a production sandbox. It must fail closed and never run imports/arbitrary attributes.
- No file upload, scraping, generated challenges, new DB/repository/service layers, custom analytics, infrastructure, dependency, CSS, or JS framework work.

## Planned implementation files

- **MODIFY** `agent/my_agent.py` — early `PROOFROUTE_STATE_V1:` Memory event action; normal chat path untouched.
- **ADD** `chatapp/app/proof_route.py` — compact models + extraction + scoring + gap + matching + snapshot codec + fixed evaluator.
- **ADD** `chatapp/app/data/riyadh_jobs.json` — 12–20 curated representative Riyadh/Saudi jobs.
- **ADD** `chatapp/app/routes/proof.py` — GET profile restore, POST profile analysis, POST fixed evaluation.
- **MODIFY** `chatapp/app/main.py` — register proof router only.
- **ADD** `chatapp/app/templates/proof.html` — one page/fragment macro using existing base/header/Tailwind/htmx.
- **ADD** `chatapp/tests/test_proof_route.py` — focused unit, Hypothesis, evaluator, and minimal route tests.

Everything else listed in the design is REUSE unchanged or DEFER.

## Deterministic contracts

- Readiness: `round(100 * demonstrated positive-frequency weight / all positive-frequency weight)`, clamped 0–100; zero denominator returns 0.
- Gap priority: `frequency * 1.0` for Missing, `frequency * 0.7` for Unverified; select descending priority then ascending canonical name.
- Match: demonstrated coverage of required skills; matched at `>= 0.60`; sort descending coverage then title/id.
- Promotion: only fixed challenge status `passed` changes Automated Testing to Demonstrated; score and matches cannot decrease.
- Memory: actor = authenticated Cognito user ID; fixed session = `proof-route-profile-v1`; message prefix = `PROOFROUTE_STATE_V1:`; newest valid schema-v1 snapshot wins.

## First implementation sequence

Seed/contracts → pure domain core → constrained evaluator → agent Memory action → route/main registration → template → focused tests → integration fixes → demo rehearsal. Follow the risk/cut list in `design.md`; cut exact `64→73`/`8→14` fixture tuning and UI polish before cutting the deterministic closed loop.

## Known risks and deferred work

- AgentCore event persistence needs one deployed smoke test; on failure show “progress not saved,” do not add a database.
- If safe Python AST containment exceeds 20 minutes, accept a structured assertion/case submission rather than unrestricted source.
- Exact demo numbers are secondary to deterministic monotonic improvement.
- Production sandboxing, multiple challenges, semantic/episodic Memory records, retries/SLAs, KB job ingestion, live market data, and richer navigation remain deferred.
