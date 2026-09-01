# Repository Project State

## Current phase

- Active spec: `proof-route` (`requirements-first`, feature).
- Authoritative artifacts: `.kiro/specs/proof-route/requirements.md`, `.kiro/specs/proof-route/design.md`, and `.kiro/specs/proof-route/.config.kiro`.
- Backend MVP implemented and locally verified. The spec directory currently has no `tasks.md`.
- Frontend template, production Riyadh dataset, formal ProofRoute tests, and AgentCore state-action branch remain teammate-owned/not yet present.
- No AgentCore agent, AWS/CDK, frontend, dataset, or teammate test file was modified by the backend batch.

## Implemented backend

- `chatapp/app/proof_route.py` now owns typed immutable models, stable serialization, deterministic CV extraction, synonym canonicalization/deduplication, market frequencies, readiness, matching, gap selection, the fixed Automated Testing challenge, the constrained evaluator, pass-gated transition/diff, and schema-v1 snapshot codec.
- `chatapp/app/routes/proof.py` now exposes authenticated `GET /proof`, `POST /proof/profile`, and `POST /proof/evaluate` routes. It restores snapshots best-effort, emits predictable template context, and returns an explicit JSON representation when `templates/proof.html` is absent.
- `chatapp/app/main.py` only imports and registers `proof_router`; existing routes and lifecycle remain unchanged.
- `docs/PROJECT_STATE.md` records the implemented integration contracts and verified limits.
- A workspace-local `.venv` was created from the existing `chatapp/requirements.txt`; no manifest was changed.

## Deterministic domain contracts

- Target role: `Junior Backend Engineer — Riyadh`.
- CV input: 50–10,000 characters. Extraction is phrase-safe and case-insensitive. A same-sentence project/repository/role/certification/implementation/measurable-outcome marker is required for `Demonstrated`; otherwise an explicit claim is `Unverified`. Absent market skills at frequency >=40 become `Missing`.
- Readiness remains the source-of-truth formula: rounded demonstrated positive-frequency weight divided by all positive-frequency weight, clamped 0–100; zero denominator returns 0.
- Match coverage is demonstrated required skills divided by all required skills; a strong match is coverage >=0.60. Ordering is coverage descending, then title/id.
- Gap score is deterministic: requirement base `frequency × (1.0 Missing | 0.7 Unverified)`, plus 3 points per candidate-near-match opportunity capped at 15. Automated Testing gets only a transparent 1.03 challenge-feasibility multiplier; the final score is capped at 100 and alphabetical ordering breaks ties. It is not hardcoded as the winner.
- The immutable challenge requires `test_normalize_status(normalize_status)` to verify trimming, lowercasing, `ok → passed`, `error → failed`, and non-string `TypeError` behavior.
- Evaluation accepts exactly one one-argument test function and a narrow AST subset. Imports, attributes, dunders, arbitrary calls, loops, assignments, comprehensions, classes, lambdas, async/yield, and other syntax are rejected before execution. Accepted source runs under `sys.executable -I` in an owner-only temporary directory with a 3-second total timeout and 10,000-character stdout/stderr bounds.
- Passing requires accepting the correct implementation and rejecting all fixed mutants: no trim, no lowercase, wrong mapping, and no type rejection.
- Only a `passed` Automated Testing result promotes that existing skill. Failed/error results preserve the profile. Promotion recomputes readiness and strong matches, reports newly matched/improved jobs, and enforces non-decrease invariants.

## Market dataset contract for Mahmoud

`chatapp/app/data/riyadh_jobs.json` is preferred automatically whenever it contains valid records. Supported root shapes are a list or `{ "jobs": [...] }`. Each record should be:

```json
{
  "id": "stable-unique-id",
  "title": "Junior Backend Engineer",
  "company": "Example Employer",
  "location": "Riyadh",
  "required_skills": ["Python", "REST APIs", "SQL", "Automated Testing"]
}
```

- `skills` is accepted as a compatibility alias for `required_skills`.
- IDs, titles, and locations must be non-empty strings; skills must be a non-empty list of strings.
- `company` is optional. A supplied string is whitespace-trimmed; missing, empty, or non-string values normalize to `""` and do not invalidate an otherwise valid job record.
- Skills are canonicalized through the backend synonym map; malformed records are skipped, duplicate IDs keep the first valid record, and output is an immutable tuple sorted by title/id.
- Until a valid file exists, the module uses a six-record constant explicitly marked `TEMPORARY DEVELOPMENT FALLBACK`. It never writes or creates the teammate-owned data file.
- Formal tests can import the public names in `app.proof_route.__all__`; loader tests should pass a temporary path rather than create the production dataset.

## Template context contract for Mashary

When `chatapp/app/templates/proof.html` exists, every endpoint renders it. `partial` is `true` for `HX-Request: true`, allowing the template to choose a fragment; otherwise it can extend `base.html`. Until then, endpoints return JSON with `X-ProofRoute-Representation: json-fallback`.

Stable context keys:

- Identity/page: `request`, `partial`, `user_email`, `is_admin`, `target_role`, `has_profile`, `proof_session_id`, `dataset_source`.
- Profile: `profile`/`profile_data` (same serialized object), `readiness`, and `skill_groups` with exactly `Demonstrated`, `Unverified`, and `Missing` keys.
- Gap: `gap`, `gap_reason`, and `market_relevance` (`frequency`, `near_match_opportunities`, `priority_score`).
- Challenge/input: `challenge`/`challenge_data`, `cv_text`, `code_submission`, and `snapshot_message`. Evaluation forms must post `code` (or `code_submission`) and preserve the hidden `snapshot_message` while server persistence is unavailable.
- Results: `evaluation`/`evaluation_data`, `transition`/`diff`, `matches` (up to 10), and `strong_match_count`. Every serialized match preserves `job_id`, `title`, `coverage`, `matched`, and `required_skills`, and also exposes dataset-backed `company`, `location`, `matched_skills` (Demonstrated requirements), `unverified_skills` (Unverified requirements), and `missing_skills` (all remaining requirements).
- Errors/persistence: `validation_errors` (field-to-message mapping), `persistence_status`, and `persistence_warning`.

Normal form and JSON bodies are both supported. Profile input is `cv_text`. The no-profile response intentionally has `has_profile=false`; the template should render only the CV CTA as its primary action.

## AgentCore contract for Burhan

- Snapshot prefix: `PROOFROUTE_STATE_V1:` followed by compact, sorted schema-v1 JSON.
- Actor ID: authenticated `request.state.user.user_id`.
- Fixed session ID: `proof-route-profile-v1`.
- Retrieval already uses `MemoryClient.get_events` and accepts current `MemoryEvent` objects, direct dictionaries, message envelopes, and AgentCore conversational payloads. Newest valid snapshot wins; malformed/unrelated events are ignored.
- Persistence is deliberately disabled unless deployment sets `PROOFROUTE_STATE_ACTION_ENABLED=true`.
- A compatible agent branch must detect the prefix **before model construction**, validate/store the event, and emit the exact text acknowledgement `PROOFROUTE_STATE_SAVED_V1` using existing stream events. Only that acknowledgement marks persistence `saved`.
- The current `agent/my_agent.py` has no such branch. Therefore the backend does not invoke the ordinary AgentCore/LLM path and returns an explicit persistence warning instead of pretending success. No agent file was modified.

## Verification completed

- The workspace `.venv` has dependencies installed from both unchanged manifests, `chatapp/requirements.txt` and `agent/requirements.txt`; `pip check` reports no broken requirements.
- `cdk/npm install` completed from the existing package manifests with zero reported vulnerabilities.
- `py_compile` passed for `proof_route.py`, `routes/proof.py`, and `main.py`.
- Inline checks passed for representative extraction, synonym dedupe, evidence states, malformed job skipping/canonicalization, repeated readiness/gap/match determinism, unsafe-source rejection, weak-test failure, strong-test pass, failed-result non-promotion, passed-result promotion, monotonic readiness/matches, snapshot round-trip, malformed/newer event handling, and application import.
- The full existing Python suite passed: 52 tests.
- CDK `npm run build` passed.
- The CDK Jest suite passed: 10 tests.
- Final authenticated/dev-mode FastAPI `TestClient` smoke passed `GET /health`, `GET /proof`, `POST /proof/profile`, and `POST /proof/evaluate`; OpenAPI verification confirmed that `/chat` and all ProofRoute paths remain registered. With no template, ProofRoute correctly returned the JSON fallback.
- The deterministic smoke produced real computed movement from readiness 52 to 67 and strong matches 2 to 3 using the temporary fallback dataset and demo CV. These are smoke-fixture results, not hardcoded product targets or business invariants.
- Local in-process application startup logged an expected optional app-settings retrieval warning because no deployed AWS settings service was used; route construction and requests succeeded.
- No persistent server was started. Application runnability was verified in-process because external AWS deployment and credentials remain teammate/manual integration territory.

## Limitations and next steps

- The fallback dataset is for development only; replace it by adding the teammate-owned JSON file under the documented schema and rerun domain/formal tests.
- Progress across requests/browser sessions is not guaranteed until the agent state-action contract is deployed and explicitly enabled. The current response remains usable through `snapshot_message`.
- AgentCore Memory and deployed runtime behavior still need an AWS smoke using a real authenticated user, configured Memory ID/runtime ARN, and the Burhan acknowledgement branch.
- `snapshot_message` is client-carried MVP state when persistence is unavailable; production should add integrity/conflict controls.
- The AST-constrained evaluator is demo containment, not a production multi-tenant sandbox.
- Next integration step: add `proof.html`, the real job dataset, the agent prefix branch, and teammate-owned formal tests without changing the deterministic backend contracts above.
