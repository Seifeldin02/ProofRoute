# Implementation Plan: ProofRoute AWS SkillForge Correction

## Overview

This plan continues the existing ProofRoute requirements-first spec. It does not restart or replace the implemented backend. The mandatory read-only SkillForge verification gate runs first; every new AWS integration, UI enhancement, or infrastructure-related change depends on a recorded gate PASS. AWS-dependent tasks fail safely when credentials are missing or expired: record the exact sanitized blocker and manual refresh command, do not claim success, do not deploy a substitute, and do not push.

Implementation uses Python for the FastAPI/Strands agent and TypeScript only for validating the existing CDK application. Exact SSM parameter paths must be discovered from the official `/app/workshop` SkillForge inventory in `us-west-2`; illustrative `citypulse` names are not configuration authority.

## Tasks

- [x] 1. Preserve completed deterministic backend context
  - [x] 1.1 Keep the implemented ProofRoute domain and evaluator unchanged as the reference core
    - Preserve canonical extraction, deterministic frequency/readiness/gap/match formulas, fixed Automated Testing challenge, AST allowlist, hidden mutants, timeout/output bounds, pass-gated transition, and snapshot codec in `chatapp/app/proof_route.py`.
    - _Requirements: 3.1–3.7, 4.1–4.4, 5.1–5.5, 7.1–7.9, 9.1–9.6, 12.1–12.7, 13.1–13.7, 20.1_
  - [x] 1.2 Keep the implemented authenticated ProofRoute routes and registration as integration context
    - Preserve `GET /proof`, `POST /proof/profile`, `POST /proof/evaluate`, fallback serialization, and `chatapp/app/main.py` router registration.
    - _Requirements: 1.1–1.7, 10.1, 10.6–10.7_
  - [x] 1.3 Retain the validated local Riyadh dataset fallback contract
    - Preserve canonicalization, malformed-record rejection, deterministic source behavior, and explicit development fallback labeling until the official market path is verified.
    - _Requirements: 18.4–18.6_

- [ ] 2. Implement and execute the mandatory SkillForge verification gate
  - [ ] 2.1 Create the name-only SkillForge parameter manifest and typed configuration resolver
    - Add a manifest format containing only exact SSM paths and seven logical roles: Code Interpreter, Gateway, Knowledge Base, Memory, two DynamoDB tables, and S3 bucket.
    - Resolve values at runtime in `us-west-2`, enforce one-to-one role mapping, validate resource identifier types, and fail closed on absent, duplicate, empty, malformed, or wrong-role entries.
    - Do not commit resolved values, credentials, tokens, or secrets.
    - _Requirements: 14.5–14.6, 14.11, 14.13, 15.1–15.6_

  - [ ] 2.2 Add a non-mutating credential-first verification command
    - Implement profile discovery, explicit `us-west-2` selection, STS identity verification, `/app/workshop` metadata listing, seven-parameter reconciliation, and suppressed-value resolution.
    - Verify through official read-only APIs that the SkillForge KB is `ACTIVE`; Code Interpreter, Gateway, Memory, both DynamoDB tables, and the S3 bucket are accessible.
    - Classify authentication/SSO/token/authorization errors before resource errors and emit only sanitized evidence.
    - Allowlist read-only commands; include no deploy, bootstrap, create, update, import, write, or delete operation.
    - _Requirements: 14.2–14.11, 21.1–21.4_

  - [ ] 2.3 Write verification and configuration tests
    - Implement **Property 9: SkillForge configuration resolves exactly one verified value per role or fails closed** with at least 100 Hypothesis examples.
    - Implement credential-error classification, exact-seven boundary, redaction, conflicting `citypulse` example, read-only command allowlist, and local-mode example tests.
    - Tag property tests with the required feature/property comment.
    - _Requirements: 14.2–14.11, 15.1–15.6_

  - [ ] 2.4 Execute the Verification_Gate and record sanitized evidence
    - Detect named profiles, select the SkillForge-authorized profile, use `us-west-2`, verify STS identity, enumerate `/app/workshop`, and resolve/verify all seven official parameters without displaying values.
    - If credentials are missing or expired, stop and record the exact sanitized failing command plus the appropriate manual command, such as `aws sso login --profile <skillforge-profile>`; mark the gate BLOCKED and do not run dependent tasks.
    - If the inventory or any required resource cannot be verified, record BLOCKED without creating a replacement or claiming AWS success.
    - Update `docs/PROJECT_STATE.md` with profile name, region, account/principal evidence, exact parameter names, resource-role statuses, KB status, timestamp, and blockers, excluding values and secrets.
    - _Requirements: 14.1–14.13, 21.4–21.6_

  - [ ] 2.5 Identify shared-resource overlap without changing infrastructure
    - Compare verified resource metadata with current Starter Kit/CDK resources and record resource type, sanitized identifier fingerprint, ownership evidence, and `reuse-only` disposition.
    - Do not delete, import, recreate, replace, deploy, or alter any overlapping Runtime, Memory, Gateway, Code Interpreter, KB, table, bucket, Cognito, Guardrail, or observability resource.
    - Add the overlap findings to `docs/PROJECT_STATE.md`.
    - _Requirements: 16.6, 21.1–21.6_

- [ ] 3. Add verified managed tool adapters after gate PASS
  - [ ] 3.1 Implement the versioned deterministic calculation bundle
    - Extract a bounded Python calculation contract that reproduces existing frequency, readiness, priority, alphabetical tie-break, matching, monotonicity, and ordered planning rules.
    - Add schema version, calculation version, input digest, market source, diagnostics, and strict result validation.
    - Keep the existing local pure functions as the reference oracle and labeled fallback.
    - _Requirements: 4.1–4.4, 5.1–5.5, 9.1–9.6, 17.2–17.5, 17.8_

  - [ ] 3.2 Integrate real AgentCore Code Interpreter through Strands
    - Add a managed Code Interpreter tool adapter using the verified SSM-resolved resource and official Strands integration.
    - Send only bounded structured profile/market inputs; reject schema, digest, range, ordering, and monotonicity violations.
    - Expose no challenge-grade or Skill_State-promotion operation and label local fallback truthfully when managed execution is unavailable.
    - _Requirements: 16.1–16.5, 17.1–17.8, 20.2_

  - [ ] 3.3 Integrate the official SkillForge KB through AgentCore Gateway
    - Add a Gateway MCP market adapter using the verified Gateway and SkillForge KB configuration.
    - Normalize bounded market evidence, preserve supplied source references, and emit `skillforge-kb` only after successful verified retrieval.
    - Route failures to the existing validated local loader with `local-fallback` and a sanitized reason; never imitate an AWS result.
    - _Requirements: 2.2–2.6, 16.1–16.5, 18.1–18.6_

  - [ ] 3.4 Implement scoped AgentCore Memory access
    - Scope every read/write by authenticated user ID, `proof-route` namespace, and stable ProofRoute session.
    - Store versioned profile/plan/outcome/source records with UTC timestamp and idempotency/input digest.
    - Reject missing identity and cross-actor/namespace records; preserve visible in-request state with an unavailable label on failure.
    - _Requirements: 8.1–8.6, 19.1–19.6_

  - [ ] 3.5 Write managed-adapter contract and property tests
    - Implement **Property 10: Managed-compatible calculation is deterministic and reference-equivalent**, **Property 12: Market source labels and citations remain truthful**, and **Property 13: ProofRoute Memory scope isolates candidates**, each as one Hypothesis test with at least 100 examples.
    - Add examples for Code Interpreter outage, malformed result, Gateway outage, source-reference preservation, missing identity, cross-user record, and Memory outage.
    - Mock AWS for unit/property tests; reserve real service calls for the bounded smoke task.
    - _Requirements: 17.2–17.8, 18.2–18.6, 19.1–19.6_

- [ ] 4. Implement one-agent autonomous ProofRoute orchestration
  - [ ] 4.1 Build the ProofRoute orchestration state machine around one Strands agent
    - Add structured workflow decisions for profile initialization, market retrieval, exact calculation/planning, challenge presentation, deterministic evaluation, pass-gated promotion, recalculation, and scoped persistence.
    - Validate every tool result before dependent calls and preserve the last verified state on any failure.
    - Keep the deterministic evaluator as the only challenge authority.
    - _Requirements: 3.5–3.6, 6.1–6.7, 7.1–7.9, 16.1–16.6, 17.6–17.7_

  - [ ] 4.2 Wire the orchestrator into the existing AgentCore entrypoint
    - Register the verified Gateway, Code Interpreter, deterministic evaluator, profile, and scoped Memory tools on the existing agent/runtime only.
    - Preserve existing Guardrails, stream event types, chat behavior, Runtime ARN, model configuration, and compatibility snapshot action without creating a second agent or entrypoint.
    - _Requirements: 10.1–10.7, 11.1–11.6, 16.1, 16.5–16.6_

  - [ ] 4.3 Connect the ProofRoute FastAPI flow to structured orchestration results
    - Update existing routes to consume validated agent results, source/calculation labels, ordered plan, persistence status, and failure diagnostics while preserving deterministic in-request fallback behavior.
    - Do not expose resource identifiers, SSM values, raw tool payloads, or infrastructure internals to the browser.
    - _Requirements: 1.1–1.7, 9.1–9.6, 10.1–10.7, 17.3, 18.2–18.6, 19.6_

  - [ ] 4.4 Write orchestration and authority-boundary tests
    - Implement **Property 11: Orchestration failure cannot advance dependent tools or verified state** with at least 100 Hypothesis examples.
    - Test no-profile, verified-profile, malformed tool result, Gateway fallback, Code Interpreter fallback, evaluator fail/pass, persistence failure, unchanged normal chat stream parsing, and absence of a Code Interpreter promotion path.
    - _Requirements: 16.1–16.6, 17.3–17.8, 18.4–18.6, 19.6_

- [ ] 5. Add lightweight Arabic RTL and sanitized observability
  - [ ] 5.1 Add Arabic presentation to the existing ProofRoute template
    - Translate primary headings, actions, status labels, validation messages, and result summaries using the existing Jinja/htmx page.
    - Apply RTL to Arabic prose and explicit LTR to code, identifiers, hashes, and numeric/formula blocks; preserve English behavior and 1280px responsive layout.
    - Add no new frontend framework, translation service, or duplicate page.
    - _Requirements: 10.2–10.7, 20.3–20.5_

  - [ ] 5.2 Instrument ProofRoute tool operations through existing observability paths
    - Emit sanitized operation, duration, status, fallback/source label, correlation hash, and logical resource role for Runtime, Gateway, Code Interpreter, Memory, and evaluator calls.
    - Exclude CV text, submitted code, evidence snippets, credentials, SSM values, raw Memory records, and raw tool payloads.
    - _Requirements: 20.2, 20.6–20.7_

  - [ ] 5.3 Write Arabic UI, redaction, and observability tests
    - Implement **Property 14: Sensitive values are absent from tool payloads and observability output** with at least 100 Hypothesis examples.
    - Add Arabic/English render tests, RTL/LTR DOM assertions, htmx fragment regression, 1280px browser smoke coverage, and sanitized span examples.
    - _Requirements: 15.4–15.5, 19.5, 20.2–20.7_

- [ ] 6. Checkpoint — Ensure all implementation tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Complete mandatory validation, documentation, and guarded push
  - [ ] 7.1 Run credential and secret scanning before validation
    - Scan tracked changes, name-only manifest, generated gate report, templates, logs/fixtures, and git diff with the repository-approved secret scanner plus forbidden credential/token/value patterns.
    - If any material is found, block commit/push, remove it, and document sanitized remediation; never print the value.
    - _Requirements: 14.2, 14.6, 15.4–15.5, 20.2, 20.7, 21.7–21.8_

  - [ ] 7.2 Run targeted ProofRoute tests and deterministic smoke
    - Run all ProofRoute unit, property, route, evaluator, orchestration, UI, redaction, and fallback tests in non-watch mode.
    - Verify CV → profile → fixed challenge fail → fixed challenge pass → promotion → diff while preserving existing deterministic authority.
    - Record exact commands and pass/fail summaries in `docs/PROJECT_STATE.md`.
    - _Requirements: 1.1–1.7, 3.1–3.7, 4.1–4.5, 5.1–5.6, 7.1–7.9, 9.1–9.6, 10.1–10.7, 12.1–12.7, 13.1–13.7_

  - [ ] 7.3 Run the full repository test and build matrix
    - Run the complete Python test suite, Python compile/import checks, CDK TypeScript build, and CDK Jest suite without watch mode.
    - Confirm synthesized infrastructure introduces no duplicate shared foundation resources and no unintended destructive changes.
    - Record failures exactly and block push until resolved.
    - _Requirements: 16.6, 21.1–21.4, 21.7–21.8_

  - [ ] 7.4 Run authorized non-destructive SkillForge smoke checks
    - Reconfirm STS identity and gate PASS with the same named profile in `us-west-2` immediately before AWS smoke.
    - Execute one bounded Gateway query against the verified ACTIVE SkillForge KB, one real Strands Code Interpreter calculation, and one scoped test-actor Memory write/read using approved non-production test data; verify both DynamoDB tables and S3 bucket only with non-destructive access checks.
    - If credentials are missing/expired or any resource cannot be verified, mark BLOCKED, record the sanitized command/error and manual refresh command, do not claim success, do not deploy/recreate anything, and do not push.
    - _Requirements: 14.2–14.12, 17.1, 18.1–18.2, 19.1–19.4, 21.1–21.8_

  - [ ] 7.5 Finalize project-state and traceability documentation
    - Update `docs/PROJECT_STATE.md` with sanitized gate evidence, exact parameter names but no values, overlap/reuse decisions, implementation files, source/fallback behavior, calculation/evaluator authorities, test/build/smoke results, and unresolved blockers.
    - Cite verified official resources and distinguish observed AWS behavior from local fallback behavior.
    - _Requirements: 14.12–14.13, 18.2–18.6, 21.2, 21.5–21.8_

  - [ ] 7.6 Enforce final evidence and push gate
    - Implement and run **Property 15: Verification evidence gates AWS claims and push eligibility** with at least 100 generated status combinations.
    - Review git status/diff, ensure only intended files are staged, and confirm verification, secret scan, tests, build, integration, smoke, and documentation are all PASS.
    - Push only after all required evidence is PASS and the user has explicitly authorized the target branch/remote at execution time; otherwise stop with the exact sanitized blocker and manual next step.
    - _Requirements: 21.5–21.8_

- [ ] 8. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Completed Task 1 records existing work and is intentionally absent from the dependency graph.
- Tasks 2.1–2.5 are the only work permitted before the Verification_Gate passes; they create and execute the gate itself.
- Tasks in waves after 4 must not start unless Task 2.4 records PASS. A BLOCKED gate pauses the DAG.
- Exact SkillForge SSM parameter paths are discovered from `/app/workshop`; do not invent names from illustrative commands.
- No task deploys, recreates, imports, deletes, or replaces shared foundation resources.
- Tests are mandatory for this correction and are not marked optional because verification and secret safety are release gates.
- AWS-dependent validation never converts missing/expired credentials into a skipped pass.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1"] },
    { "id": 1, "tasks": ["2.2"] },
    { "id": 2, "tasks": ["2.3"] },
    { "id": 3, "tasks": ["2.4"] },
    { "id": 4, "tasks": ["2.5"] },
    { "id": 5, "tasks": ["3.1", "3.3", "3.4", "5.1"] },
    { "id": 6, "tasks": ["3.2"] },
    { "id": 7, "tasks": ["3.5", "4.1", "5.2"] },
    { "id": 8, "tasks": ["4.2", "5.3"] },
    { "id": 9, "tasks": ["4.3"] },
    { "id": 10, "tasks": ["4.4"] },
    { "id": 11, "tasks": ["7.1"] },
    { "id": 12, "tasks": ["7.2"] },
    { "id": 13, "tasks": ["7.3"] },
    { "id": 14, "tasks": ["7.4"] },
    { "id": 15, "tasks": ["7.5"] },
    { "id": 16, "tasks": ["7.6"] }
  ]
}
```
