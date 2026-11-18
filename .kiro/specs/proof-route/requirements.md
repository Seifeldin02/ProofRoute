# Requirements Document

## Introduction

ProofRoute is an evidence-driven career agent built on top of the `aws-samples/sample-strands-agentcore-starter` kit. It targets recent graduates and early-career software engineering candidates — specifically those in Riyadh pursuing junior backend/software engineering roles — by replacing self-reported skill claims with verifiable proof.

The core loop: a candidate pastes their CV → ProofRoute classifies every relevant skill as Demonstrated / Unverified / Missing → the agent selects the highest-impact gap → it generates a short coding challenge with deterministic success criteria → the candidate submits code → the agent executes it against test cases → if passing, the skill transitions to Demonstrated → readiness score and job matches recalculate → the before/after diff is surfaced → the agent recommends the next action.

ProofRoute is delivered as a dedicated dashboard page within the existing chatapp (htmx + FastAPI). It reuses all deployed infrastructure: AgentCore Runtime, AgentCore Memory (episodic + semantic strategies), Bedrock Knowledge Base (seeded with job market data), Bedrock Guardrails, and CDK stacks. No new infrastructure is created.

Demo target: Backend Readiness 64% → 73%, Automated Testing Unverified → Demonstrated, Job Matches 8 → 14.

---

## Glossary

- **Candidate**: A recent graduate or early-career software engineer using ProofRoute.
- **CV_Parser**: The agent tool responsible for extracting raw skill claims from candidate-provided CV text.
- **Skill_Extractor**: The agent component that normalizes extracted skills, maps them against market data, and assigns initial skill states.
- **Skill_State**: One of three values — `Demonstrated`, `Unverified`, or `Missing` — assigned to each skill in a candidate's profile.
- **Skill_Profile**: The full set of a candidate's skills with their states, market frequency, and evidence sources.
- **Readiness_Scorer**: The deterministic component that computes a candidate's Career Readiness Score from their Skill_Profile.
- **Career_Readiness_Score**: An integer in the range 0–100 representing how closely a candidate's demonstrated skills match the target market's demands.
- **Gap_Selector**: The deterministic component that identifies the highest-impact skill gap from the Skill_Profile and market data.
- **Challenge_Generator**: The agent tool that produces a short coding challenge (< 30 minutes) with explicit success criteria for a given skill gap.
- **Code_Evaluator**: The agent tool that executes candidate-submitted Python code against deterministic test cases inside the container's subprocess environment.
- **Memory_Store**: The AgentCore Memory service (existing episodic + semantic strategies) used to persist Skill_Profiles, challenge outcomes, and candidate progression across sessions.
- **Job_Market_KB**: The Bedrock Knowledge Base seeded with 20–30 Markdown job description documents targeting Riyadh/Saudi junior backend roles.
- **ProofRoute_Dashboard**: The dedicated htmx page within the existing chatapp that presents the candidate overview, skill state cards, readiness gauge, challenge widget, evaluation result, before/after diff, and job matches.
- **Proof_Challenge**: A bounded coding exercise (Python, < 30 min) generated for a specific skill gap, with explicit pass/fail criteria that the Code_Evaluator can verify deterministically.
- **Starter_Kit**: The `aws-samples/sample-strands-agentcore-starter` project providing FastAPI + htmx frontend, Strands Agents SDK, AgentCore Runtime, Memory, KB, Guardrails, and CDK stacks.
- **ProofRoute_Agent**: The single Strands agent that autonomously orchestrates ProofRoute tools through the existing AgentCore Runtime without creating a second agent or runtime.
- **AgentCore_Code_Interpreter**: The official managed Amazon Bedrock AgentCore Code Interpreter used by the ProofRoute_Agent to execute versioned deterministic scoring and planning code; the AgentCore_Code_Interpreter does not determine coding-challenge pass/fail.
- **Deterministic_Evaluator**: The existing constrained local evaluator whose deterministic hidden tests remain the sole authority for Proof_Challenge pass/fail and Skill_State promotion.
- **SkillForge_KB**: The official SkillForge Amazon Bedrock Knowledge Base identified by the authoritative SkillForge SSM configuration in `us-west-2`.
- **Market_Gateway_Tool**: The AgentCore Gateway tool that exposes the SkillForge_KB to the ProofRoute_Agent using the official managed Knowledge Base connector.
- **Local_Market_Fallback**: The existing validated local Riyadh job dataset used only when the SkillForge_KB or Market_Gateway_Tool is unavailable; responses using the fallback identify the data source and do not claim live AWS retrieval.
- **SkillForge_Parameter_Manifest**: The seven exact SSM parameter paths under `/app/workshop` supplied by or discovered from the official SkillForge workshop environment and recorded by name and logical resource role without recording secret values. The required logical roles are AgentCore Code Interpreter, AgentCore Gateway, SkillForge_KB, AgentCore Memory, two DynamoDB tables, and one S3 bucket; actual parameter paths and resource identifiers must be discovered and verified rather than inferred.
- **Verification_Gate**: The mandatory read-only AWS environment verification that must pass after the current integration work and before any new ProofRoute feature or infrastructure work begins.
- **Shared_Foundation**: The pre-existing SkillForge and Starter_Kit AWS resources, including Runtime, Memory, Gateway, Code Interpreter, SkillForge_KB, DynamoDB tables, S3 bucket, Cognito, Guardrails, and observability resources, that ProofRoute must reuse rather than deploy or recreate.
- **Scoped_Memory_Key**: The combination of authenticated user ID, ProofRoute namespace, and session identifier used to isolate each Candidate's Memory events.
- **Configuration_Resolver**: The component that loads resource identifiers from the verified SkillForge_Parameter_Manifest in SSM, validates expected identifier shape, and supplies configuration without embedding credentials or secret values in source code, logs, templates, or client responses.
- **AWS_STS**: AWS Security Token Service, used by the Verification_Gate through `GetCallerIdentity` to verify the selected profile's account and principal without exposing credentials.
- **SSM_Parameter_Store**: AWS Systems Manager Parameter Store, whose `/app/workshop` SkillForge parameters are the authoritative source of shared resource configuration.
- **DynamoDB_Table**: One of the two existing SkillForge Amazon DynamoDB tables referenced by the SkillForge_Parameter_Manifest and checked only with non-mutating verification operations.
- **S3_Bucket**: The existing SkillForge Amazon S3 bucket referenced by the SkillForge_Parameter_Manifest and checked only with non-mutating verification operations.
- **Existing_Observability**: The Starter_Kit CloudWatch and OpenTelemetry logging and tracing paths reused for sanitized ProofRoute operation telemetry.

---

## Correction Precedence

Requirements 14–21 are the urgent official AWS SkillForge correction. When an earlier criterion describes local-only market intelligence, direct arithmetic ownership, a separate ProofRoute agent entrypoint, or a generic subprocess as the complete AWS integration, Requirements 14–21 take precedence. Existing deterministic extraction, formulas, evaluator restrictions, fallback behavior, and pass-gated Skill_State transition remain valid unless explicitly refined below.

The user's `citypulse` command examples are illustrative only. The SkillForge_Parameter_Manifest discovered from the authoritative `/app/workshop` SkillForge parameters in `us-west-2` determines actual resource identifiers and names.

## Requirements

### Requirement 1: Candidate Profile Ingestion

**User Story:** As a Candidate, I want to paste my CV text into ProofRoute, so that the system can extract and classify my skills without requiring file uploads or external integrations.

#### Acceptance Criteria

1. THE ProofRoute_Dashboard SHALL provide a text input area where the Candidate can paste or type CV content of up to 10,000 characters, displaying a character count indicator that updates as the Candidate types.
2. WHEN the Candidate submits CV text containing between 50 and 10,000 characters, THE CV_Parser SHALL extract all claimed skills and work/project evidence within 30 seconds.
3. WHEN the CV_Parser completes extraction, THE Skill_Extractor SHALL assign an initial Skill_State of `Unverified` to each extracted skill that lacks a verifiable artifact reference in the CV text, and `Demonstrated` to each skill accompanied by a concrete artifact reference such as a project name, repository link, publication, or employer-verifiable role described in the CV text.
4. IF the CV text is empty or contains fewer than 50 characters, THEN THE ProofRoute_Dashboard SHALL reject submission and display a validation message instructing the Candidate to provide more detail before proceeding, leaving the input area and any previously entered text unchanged.
5. IF the CV text exceeds 10,000 characters, THEN THE ProofRoute_Dashboard SHALL reject submission and display a validation message indicating the character limit has been exceeded, leaving the input area content unchanged.
6. WHEN skill extraction completes, THE ProofRoute_Dashboard SHALL display the extracted Skill_Profile listing each skill's name, initial Skill_State, and the verbatim source evidence snippet from the CV text from which that skill was extracted.
7. IF the CV_Parser fails to complete extraction within 30 seconds, THEN THE ProofRoute_Dashboard SHALL display an error message indicating that extraction failed, preserve the submitted CV text in the input area, and allow the Candidate to resubmit.

---

### Requirement 2: Job Market Intelligence

**User Story:** As a Candidate, I want ProofRoute to analyze current market demand, so that my skill gap assessment reflects what real employers in Riyadh are hiring for.

#### Acceptance Criteria

1. THE Job_Market_KB SHALL contain at least 20 Markdown documents, each representing a distinct junior backend or software engineering job description targeting Riyadh or the Saudi market, where each document includes at least one named technical skill.
2. WHEN the Skill_Extractor initializes a Skill_Profile, THE Skill_Extractor SHALL query the Job_Market_KB and compute the market frequency of each skill as the percentage of job description documents that mention that skill, rounded to the nearest integer.
3. THE Skill_Extractor SHALL assign a `Missing` Skill_State to any skill that has a computed market frequency of 40 or greater and is absent from the candidate's CV.
4. WHEN a skill's market frequency is computed, THE Skill_Profile SHALL store that frequency as an integer in the range 0 to 100 inclusive, where the value represents the percentage of job description documents in the Job_Market_KB that mention the skill.
5. IF the Job_Market_KB ingestion has not completed successfully, THEN THE ProofRoute_Dashboard SHALL reject all access attempts and display an error message indicating that market data is unavailable.
6. WHEN the Skill_Extractor queries the Job_Market_KB and the KB returns fewer than 20 documents, THE Skill_Extractor SHALL abort Skill_Profile initialization and return an error indicating insufficient market data.

---

### Requirement 3: Evidence-Aware Skill Model

**User Story:** As a Candidate, I want each skill in my profile to carry a clear evidence state, so that I understand what I have proven, what I have claimed, and what I am missing.

#### Acceptance Criteria

1. THE Skill_Profile SHALL represent each skill as a record containing: skill name (non-empty string), Skill_State (exactly one of `Demonstrated`, `Unverified`, or `Missing`), market frequency (integer 0–100), priority score (numeric 0–100), and evidence source (CV snippet up to 500 characters, challenge outcome ID, or empty string for `Missing` skills).
2. WHEN the CV_Parser processes CV text, THE Skill_Extractor SHALL assign the `Demonstrated` state only to skills for which the CV text contains a concrete verifiable artifact reference — such as a named project, repository URL, employer-verifiable role, publication, or certification — directly associated with that skill.
3. WHEN the CV_Parser processes CV text, THE Skill_Extractor SHALL assign the `Unverified` state to skills explicitly claimed in the CV text that lack any verifiable artifact reference as defined in criterion 2.
4. WHEN market frequency data is available and a skill's computed market frequency meets or exceeds the threshold defined in Requirement 2.3, THE Skill_Extractor SHALL assign the `Missing` state to that skill if it is absent from the candidate's CV claims.
5. WHEN a Skill_State transition from `Unverified` or `Missing` to `Demonstrated` is requested, THE Skill_Extractor SHALL reject the transition unless a passing Code_Evaluator result for that skill exists in the Memory_Store, and SHALL return an error message identifying the missing evaluation result.
6. IF the Memory_Store is unavailable when a Skill_State transition is requested, THEN THE Skill_Extractor SHALL reject the transition, leave the Skill_State unchanged, and return an error message indicating that evidence verification could not be completed.
7. THE Skill_State and evidence source of every skill in a Skill_Profile retrieved from Memory_Store SHALL be identical to the corresponding values at the time the Skill_Profile was last written to Memory_Store.

---

### Requirement 4: Career Readiness Scoring

**User Story:** As a Candidate, I want to see a single readiness score, so that I can quickly understand how prepared I am for the jobs I am targeting.

#### Acceptance Criteria

1. THE Readiness_Scorer SHALL compute the Career_Readiness_Score using the formula: `score = round(100 × (sum of market_frequency for Demonstrated skills) / (sum of market_frequency for all skills with market_frequency > 0))`, where the result is clamped to the range 0–100.
2. THE Readiness_Scorer SHALL produce the same Career_Readiness_Score when called with identical Skill_Profile inputs that contain at least one skill with market_frequency > 0 (determinism property).
3. WHEN no skills have market_frequency > 0, THE Readiness_Scorer SHALL return a score of 0 rather than raising an error.
4. WHEN a skill transitions to `Demonstrated`, THE Readiness_Scorer SHALL recompute the Career_Readiness_Score before returning a response to the caller, and the new Career_Readiness_Score SHALL be greater than or equal to the Career_Readiness_Score computed immediately before that transition (monotonic non-decrease property).
5. THE ProofRoute_Dashboard SHALL display the Career_Readiness_Score as a visual gauge scaled from 0 to 100, showing the numeric score value and a label derived from the Skill_Profile's target job role name (for example, a profile targeting a backend role displays "Backend Readiness").

---

### Requirement 5: Highest-Impact Gap Selection

**User Story:** As a Candidate, I want ProofRoute to identify the single most valuable skill gap to address next, so that I focus my limited time on the action that moves me furthest toward employment.

#### Acceptance Criteria

1. THE Gap_Selector SHALL compute a priority score for each non-`Demonstrated` skill using the formula: `priority = market_frequency × (1 if Skill_State == 'Missing' else 0.7)`, where `market_frequency` is the integer value (0–100) stored in the Skill_Profile, and higher priority scores rank higher.
2. THE Gap_Selector SHALL select the non-`Demonstrated` skill with the highest priority score as the current gap; ties SHALL be broken by ascending alphabetical order of the skill name (A before Z) to ensure determinism.
3. THE Gap_Selector SHALL return the same selected skill name and priority score when called with identical Skill_Profile inputs (reproducibility property).
4. WHEN all skills in the Skill_Profile are in the `Demonstrated` state, THE Gap_Selector SHALL return a response indicating no gap remains, containing zero selected skills and no error condition.
5. IF market frequency data is unavailable for a skill at the time of priority score computation, THEN THE Gap_Selector SHALL exclude that skill from gap selection and include it in a list of unscored skills returned alongside the result.
6. WHEN the Gap_Selector selects a gap, THE ProofRoute_Dashboard SHALL display the selected skill name, its Skill_State, its market_frequency value, and a rationale string stating which factor (market frequency or Skill_State) most influenced the selection.

---

### Requirement 6: Proof Challenge Generation

**User Story:** As a Candidate, I want to receive a concrete coding challenge for my highest-impact skill gap, so that I have a clear, bounded task I can complete to prove that skill.

#### Acceptance Criteria

1. WHEN a gap skill is selected, THE Challenge_Generator SHALL produce a Proof_Challenge containing: a problem statement of no more than 300 words, an input/output specification defining data types and value ranges, at least three example test cases each with a distinct input and its expected output, and explicit pass criteria stating that all provided test cases must pass.
2. THE Challenge_Generator SHALL produce challenges that a junior software engineer can complete within 30 minutes, where challenge scope is limited to a single function or class with no more than 5 public methods, targeting Python 3.x as the implementation language.
3. WHEN a gap skill is selected, THE Challenge_Generator SHALL generate a challenge whose problem domain directly exercises that skill — for example, making an outbound HTTP request for "REST API" or authoring assertions for "Automated Testing" — such that the skill under test is the primary requirement for a correct solution.
4. WHEN a Proof_Challenge is generated, THE Challenge_Generator SHALL also produce a corresponding evaluation test suite as executable Python code containing at minimum the same test cases specified in the Proof_Challenge, which the Code_Evaluator will execute.
5. IF a Proof_Challenge for the same skill already exists in the Memory_Store for the current candidate, THEN THE Challenge_Generator SHALL retrieve and return the stored Proof_Challenge unchanged, and SHALL NOT invoke the generation pipeline, so that the candidate's progress is preserved across sessions.
6. IF a Proof_Challenge for the same skill does not exist in the Memory_Store for the current candidate, THEN THE Challenge_Generator SHALL store the newly generated Proof_Challenge in the Memory_Store before returning it to the caller.
7. THE ProofRoute_Dashboard SHALL display the Proof_Challenge problem statement, all example test cases, and a code submission area within a single scrollable widget, where the submission area accepts plain text input of up to 10,000 characters.

---

### Requirement 7: Executable Evidence Evaluation

**User Story:** As a Candidate, I want my code submission to be evaluated by running it against real test cases, so that the result reflects actual capability rather than subjective LLM judgment.

#### Acceptance Criteria

1. WHEN the Candidate submits Python code for a Proof_Challenge, THE Code_Evaluator SHALL execute the submitted code against the challenge's test suite using a subprocess within the container environment, with a timeout of 10 seconds per test case.
2. THE Code_Evaluator SHALL determine pass/fail based solely on whether all test cases produce the expected output, where output comparison is exact string match after stripping leading and trailing whitespace — LLM assessment SHALL NOT be used as the sole or primary evaluation criterion.
3. WHEN the submitted code raises an unhandled exception or exceeds the 10-second timeout for any test case, THE Code_Evaluator SHALL record that test case as failed with the exception type or a timeout indicator and continue evaluating remaining test cases.
4. WHEN all test cases pass, THE Code_Evaluator SHALL emit a structured evaluation result containing: overall status `passed`, per-test-case results (input, expected output, actual output, status), and the skill name.
5. WHEN at least one test case fails, THE Code_Evaluator SHALL emit a structured evaluation result containing: overall status `failed`, per-test-case results (input, expected output, actual output, status), and a plain-language hint describing the nature of the failure in the first failing test case.
6. IF the Code_Evaluator evaluation result status is `passed`, THEN THE Skill_Extractor SHALL transition the corresponding skill's Skill_State from its current state to `Demonstrated`.
7. THE Code_Evaluator SHALL not execute code with unrestricted filesystem write access outside the temporary working directory — submitted code SHALL run with restricted permissions appropriate to the container environment.
8. IF the submitted Python code is empty or exceeds 65,536 characters, THEN THE Code_Evaluator SHALL reject the submission without execution and emit an evaluation result with overall status `failed` and an error message indicating the rejection reason.
9. IF the Code_Evaluator subprocess cannot be started due to an environment error, THEN THE Code_Evaluator SHALL emit an evaluation result with overall status `error` and an error message indicating the infrastructure failure, leaving the corresponding skill's Skill_State unchanged.

---

### Requirement 8: Persistent Candidate Progression

**User Story:** As a Candidate, I want my skill states and challenge history to persist across browser sessions, so that I can continue my ProofRoute journey without losing progress.

#### Acceptance Criteria

1. WHEN a Skill_Profile is updated (new skills extracted, state transitions, or challenge outcomes), THE Memory_Store SHALL persist the full Skill_Profile under the candidate's user ID using the AgentCore Memory semantic strategy within 5 seconds of the update event.
2. WHEN a Proof_Challenge evaluation completes, THE Memory_Store SHALL persist the evaluation outcome (skill name, resulting Skill_State, pass/fail status, and UTC timestamp) as an episodic memory record associated with the candidate's user ID and session ID within 5 seconds of evaluation completion.
3. WHEN the Candidate navigates to the ProofRoute_Dashboard in a new browser session, THE ProofRoute_Dashboard SHALL retrieve the stored Skill_Profile and the most recent evaluation outcome per skill from Memory_Store and render the dashboard with the restored state within 10 seconds, without requiring CV re-submission.
4. THE Memory_Store SHALL guarantee that the Skill_State of every skill in a retrieved Skill_Profile is identical to the Skill_State of the corresponding skill at the time it was last written, with zero tolerance for state divergence.
5. IF a Memory_Store retrieval operation does not return a successful response within 10 seconds, THEN THE ProofRoute_Dashboard SHALL display an error message indicating that progress could not be loaded and present the Candidate with the option to re-submit their CV to start a new session.
6. IF a Memory_Store write operation for a Skill_Profile update or evaluation outcome does not return a successful response within 10 seconds, THEN THE Memory_Store SHALL retry the write operation up to 3 times at 2-second intervals before marking the operation as failed and notifying the ProofRoute_Dashboard of the write failure.

---

### Requirement 9: Score Recalculation and Before/After Diff

**User Story:** As a Candidate, I want to see exactly how my readiness score and job matches changed after completing a challenge, so that the impact of my effort is immediately visible and motivating.

#### Acceptance Criteria

1. WHEN a skill transitions to `Demonstrated` following a successful evaluation, THE Readiness_Scorer SHALL compute a new Career_Readiness_Score within 5 seconds of the transition event, AND THE ProofRoute_Dashboard SHALL display both the previous score and the new score side by side, where each score is a numeric value in the range 0 to 100 inclusive.
2. WHEN a skill transitions to `Demonstrated`, THE ProofRoute_Dashboard SHALL display the job match count before the transition and the job match count after the transition, where the before count reflects the candidate's matched jobs prior to the transition and the after count is calculated by counting job descriptions in the Job_Market_KB that require the newly demonstrated skill and were not already matched.
3. THE job match count after a skill is demonstrated SHALL be greater than or equal to the job match count before that transition for any given candidate and skill combination (monotonic non-decrease property).
4. THE ProofRoute_Dashboard SHALL display a before/after diff card containing all six fields: previous score, new score, score delta (calculated as new score minus previous score), previous job match count, new job match count, and the name of the demonstrated skill, where each field is visible and non-empty.
5. WHEN the Gap_Selector identifies a new highest-impact gap following recalculation, THE ProofRoute_Dashboard SHALL display the updated gap recommendation and present a single action control that, when activated by the Candidate, initiates the next Proof_Challenge without requiring additional confirmation steps.
6. IF the Readiness_Scorer fails to compute a new Career_Readiness_Score within 5 seconds of a skill transition to `Demonstrated`, THEN THE ProofRoute_Dashboard SHALL display an error message indicating the score update is unavailable and retain the previously displayed score and job match counts unchanged.

---

### Requirement 10: ProofRoute Dashboard UI

**User Story:** As a Candidate, I want a dedicated ProofRoute dashboard that shows my full progress in one place, so that I can understand my status and take action without navigating multiple pages.

#### Acceptance Criteria

1. THE ProofRoute_Dashboard SHALL be accessible at the `/proof` route within the existing chatapp and SHALL require the same Cognito authentication as the `/chat` route.
2. THE ProofRoute_Dashboard SHALL render server-side via htmx partial updates within the existing `base.html` template, consistent with the current chatapp UI patterns.
3. THE ProofRoute_Dashboard SHALL display the following sections in a single scrollable view: (a) candidate summary showing the target role and a Career_Readiness_Score gauge displaying a numeric score between 0 and 100, (b) skill state cards grouped into exactly three categories — `Demonstrated`, `Unverified`, and `Missing` — each card showing the skill name and a market frequency badge, (c) current gap highlight identifying the single highest-priority missing or unverified skill, (d) active Proof_Challenge widget containing a code submission text area accepting input between 1 and 10,000 characters, (e) evaluation result display showing the pass/fail outcome and per-test-case results, (f) before/after diff card showing score and job match changes from the most recent Proof_Challenge evaluation, (g) top job matches from the Job_Market_KB displaying between 1 and 10 job titles.
4. WHEN the ProofRoute_Dashboard initiates a data request to the agent or Memory_Store, THE ProofRoute_Dashboard SHALL display an htmx loading indicator within 200 milliseconds of the request starting and SHALL remove the indicator once the response is received.
5. THE ProofRoute_Dashboard SHALL render all sections without horizontal scrolling at a viewport width of 1280px, using only CSS classes and layout patterns already present in the existing chatapp stylesheets.
6. IF the Candidate has no stored Skill_Profile in the Memory_Store, THEN THE ProofRoute_Dashboard SHALL display a CV input prompt as the sole primary call-to-action in place of the skill state cards, gap highlight, Proof_Challenge widget, evaluation result display, before/after diff card, and job matches sections, and SHALL NOT render those sections until a Skill_Profile has been created.
7. IF the ProofRoute_Dashboard fails to load data from the agent or Memory_Store within 30 seconds of the request starting, THEN THE ProofRoute_Dashboard SHALL remove the loading indicator and display an error message indicating that data could not be retrieved, without altering any previously displayed Skill_Profile data.

---

### Requirement 11: ProofRoute Agent Entrypoint

**User Story:** As a developer, I want a dedicated ProofRoute agent entrypoint within the existing AgentCore Runtime, so that ProofRoute's agentic workflow is isolated from the general chat agent while sharing all deployed infrastructure.

#### Acceptance Criteria

1. THE ProofRoute_Agent SHALL be implemented as a separate `@app.entrypoint` decorated async function with a distinct entrypoint name within the existing `agent/` directory, registered on the same `BedrockAgentCoreApp` instance as the existing chat agent.
2. THE ProofRoute_Agent SHALL use the same AgentCore Runtime ARN, Memory ID, and Bedrock model configuration (read from the same environment variables) as the existing chat agent, consuming no additional AWS resources.
3. THE ProofRoute_Agent SHALL register the following tools in its `tools` list at agent construction time: `parse_cv`, `extract_skills`, `compute_readiness_score`, `select_gap`, `generate_challenge`, `evaluate_code`, `store_skill_profile`, `retrieve_skill_profile`.
4. WHEN the ProofRoute_Agent invokes the `evaluate_code` tool, THE Code_Evaluator SHALL execute in the same container process as the agent, using Python's `subprocess` module with a 10-second timeout per test case, and shall return a structured result to the agent even when the subprocess times out or exits with a non-zero return code.
5. WHEN the ProofRoute_Agent emits streamed events, those events SHALL use the same `type` field values (`tool_use`, `tool_result`, text delta events, and `guardrail`) that the existing AgentCore client in `chatapp/app/agentcore/client.py` already parses, so that the ProofRoute_Dashboard can consume them without changes to the client.
6. THE ProofRoute_Agent SHALL instantiate a `NotifyOnlyGuardrailsHook` using the `GUARDRAIL_ID` and `GUARDRAIL_VERSION` environment variables and register it in the agent's hooks list, applying it to all LLM calls in the same manner as the existing chat agent.

---

### Requirement 12: CV Parser and Skill Extractor Tools

**User Story:** As a developer, I want reliable CV parsing and skill extraction tools, so that the agent consistently derives a structured Skill_Profile from unstructured candidate text.

#### Acceptance Criteria

1. THE CV_Parser SHALL accept a plain-text string between 1 and 10,000 characters (inclusive) and return a structured list of (skill_name, evidence_snippet, confidence) tuples ordered by descending confidence, where confidence is a float in [0.0, 1.0].
2. IF the CV text input is empty (0 characters) or exceeds 10,000 characters, THEN THE CV_Parser SHALL reject the input and return an error indicating the input length constraint, without producing any tuples.
3. WHEN CV text contains a skill name followed by at least one sentence that includes either a measurable numeric outcome (e.g., a percentage, count, or duration) or an explicit project or role context (e.g., text containing "project", "built", "developed", "implemented", or "led"), THE CV_Parser SHALL extract that sentence as the evidence_snippet for that skill, truncated to a maximum of 300 characters.
4. THE Skill_Extractor SHALL normalize skill names to a canonical form — title-cased, whitespace-trimmed, and single-space-separated — using a predefined synonym mapping stored as a configuration file, such that variant spellings (e.g., "unit testing", "unit tests", "pytest") resolve to a single canonical entry (e.g., "Automated Testing").
5. THE CV_Parser followed by THE Skill_Extractor SHALL produce a Skill_Profile where every skill name is a non-empty string, every Skill_State is exactly one of `Demonstrated`, `Unverified`, or `Missing`, and no two entries share the same canonical skill name.
6. THE Skill_Extractor SHALL complete skill extraction and market frequency lookup within 30 seconds for a CV of up to 10,000 characters.
7. IF the market frequency lookup service is unavailable or does not respond within 5 seconds, THEN THE Skill_Extractor SHALL complete skill extraction without market frequency data, set the market_frequency field to null for all affected skills, and return a partial Skill_Profile within the remaining time budget of the 30-second limit.

---

### Requirement 13: Code Execution Security

**User Story:** As a developer, I want the code execution environment to be appropriately sandboxed within the container, so that candidate submissions cannot compromise the running application.

#### Acceptance Criteria

1. WHEN the Code_Evaluator executes candidate code, THE Code_Evaluator SHALL run the subprocess in a dedicated temporary working directory isolated from the application source directory, and delete that directory upon evaluation completion regardless of outcome.
2. THE Code_Evaluator SHALL enforce a total wall-clock timeout of 30 seconds for the entire evaluation run across all test cases combined, terminating the subprocess and all its child processes if the limit is exceeded.
3. WHEN the subprocess is terminated due to the 30-second wall-clock timeout, THE Code_Evaluator SHALL record all remaining test cases as failed with status `timeout` and include the elapsed duration in the evaluation result.
4. THE Code_Evaluator SHALL capture subprocess stdout and stderr as separate fields, each truncated to a maximum of 10,000 characters, and include both fields in the evaluation result returned to the Candidate.
5. WHEN the Code_Evaluator subprocess exits with a non-zero return code, THE Code_Evaluator SHALL mark all test cases for that run as failed with a status of `error` and include the captured stderr, truncated to 10,000 characters, as the error detail in the evaluation result.
6. WHILE the Code_Evaluator subprocess is running, THE Code_Evaluator SHALL restrict subprocess memory usage to a maximum of 512 MB, terminating the subprocess if the limit is exceeded and marking all test cases as failed with status `memory_limit_exceeded`.
7. WHEN the Code_Evaluator creates the temporary working directory, THE Code_Evaluator SHALL set directory permissions such that only the subprocess user account can read, write, and execute within that directory.


---

### Requirement 14: Mandatory SkillForge Environment Verification Gate

**User Story:** As a developer, I want the shared SkillForge environment verified before further work, so that ProofRoute integrates with real official resources without masking credential or configuration problems.

#### Acceptance Criteria

1. WHEN the current in-progress integration reaches its verification stage, THE Verification_Gate SHALL complete before any new ProofRoute feature implementation or infrastructure change begins.
2. WHEN verification begins, THE Verification_Gate SHALL detect locally configured named AWS CLI profiles and select the SkillForge-authorized profile without reading or displaying access keys, secret keys, session tokens, or SSO cached tokens.
3. WHEN the SkillForge-authorized profile is selected, THE Verification_Gate SHALL set the AWS region to `us-west-2` for every verification command and SDK client.
4. WHEN profile and region selection completes, THE Verification_Gate SHALL call AWS STS `GetCallerIdentity` and record only the account ID, principal ARN, profile name, region, command status, and timestamp.
5. WHEN STS identity verification succeeds, THE Verification_Gate SHALL list parameter metadata under `/app/workshop`, identify the seven exact SkillForge parameter paths, and map those paths to the seven logical roles in the SkillForge_Parameter_Manifest.
6. WHEN the SkillForge_Parameter_Manifest is assembled, THE Verification_Gate SHALL resolve all seven parameters and record each parameter name, logical role, version or last-modified metadata when available, and validation status without recording any parameter value.
7. WHEN resource identifiers are resolved, THE Verification_Gate SHALL verify that the SkillForge_KB status is `ACTIVE`, both referenced DynamoDB tables are describable and accessible through non-mutating operations, and the referenced S3 bucket is accessible through non-mutating metadata or listing operations.
8. WHEN the SkillForge_Parameter_Manifest references AgentCore Code Interpreter, AgentCore Gateway, or AgentCore Memory resources, THE Verification_Gate SHALL verify each referenced resource through an official read-only API before recording the gate as passed.
9. IF any AWS command returns an authentication, SSO, token-expiry, credential-process, signature, or authorization error, THEN THE Verification_Gate SHALL diagnose credentials and profile selection before diagnosing resource absence or proposing deployment.
10. IF valid credentials cannot be obtained, THEN THE Verification_Gate SHALL stop AWS-dependent work, record the exact failing command and sanitized error category, provide profile-specific manual login or credential-refresh commands, and mark every unverified AWS claim as blocked rather than passed.
11. IF fewer or more than seven authoritative SkillForge parameters are identified under `/app/workshop`, THEN THE Verification_Gate SHALL fail with a sanitized inventory mismatch and require reconciliation against the official SkillForge handoff before integration continues.
12. WHEN verification completes, THE Verification_Gate SHALL update `docs/PROJECT_STATE.md` with the sanitized evidence, pass/block status, authoritative parameter names, verified resource types, and unresolved blockers before any dependent task starts.
13. THE Verification_Gate SHALL treat any user-provided `citypulse` commands or resource names as illustrative examples and SHALL use the verified SkillForge parameters as the authoritative configuration source.

### Requirement 15: SSM-Driven SkillForge Configuration

**User Story:** As a developer, I want ProofRoute configuration resolved from the verified SkillForge SSM parameters, so that deployments use official shared resources without hard-coded identifiers.

#### Acceptance Criteria

1. THE Configuration_Resolver SHALL load all AWS resource identifiers required by ProofRoute from the seven verified entries in the SkillForge_Parameter_Manifest in `us-west-2`.
2. WHEN the Configuration_Resolver returns configuration, THE Configuration_Resolver SHALL expose typed logical fields for AgentCore Code Interpreter, AgentCore Gateway, SkillForge_KB, AgentCore Memory, two DynamoDB tables, and one S3 bucket.
3. IF an expected parameter is absent, duplicated, empty, malformed, or mapped to the wrong resource type, THEN THE Configuration_Resolver SHALL fail closed with the parameter name and sanitized reason without invoking the affected resource.
4. THE Configuration_Resolver SHALL not embed SSM values, AWS credentials, tokens, or secret material in source code, committed environment files, browser content, error responses, telemetry attributes, or logs.
5. WHEN configuration is logged for diagnostics, THE Configuration_Resolver SHALL log parameter names, resource types, region, and validation status while redacting resource values classified as secret or sensitive.
6. WHERE a non-AWS local development mode is explicitly enabled, THE Configuration_Resolver SHALL use documented local placeholders and Local_Market_Fallback data while labeling AWS integrations as unavailable and unverified.

### Requirement 16: Autonomous Single-Agent Orchestration

**User Story:** As a Candidate, I want one agent to coordinate my evidence workflow autonomously, so that market research, exact planning, evaluation, and persistence form one coherent progression.

#### Acceptance Criteria

1. THE ProofRoute_Agent SHALL use one Strands agent on the existing AgentCore Runtime to orchestrate Market_Gateway_Tool retrieval, AgentCore_Code_Interpreter scoring and planning, Deterministic_Evaluator execution, and Memory_Store persistence.
2. WHEN a Candidate submits a CV or requests the next action, THE ProofRoute_Agent SHALL determine the required tool sequence from current Skill_Profile state and tool results without requiring the Candidate to manually invoke individual tools.
3. WHEN the ProofRoute_Agent invokes a tool, THE ProofRoute_Agent SHALL validate the structured tool result before using the result in a subsequent tool call or Candidate response.
4. IF a required tool returns an error or malformed result, THEN THE ProofRoute_Agent SHALL stop dependent actions, preserve the last verified Skill_Profile, and identify the failed capability without fabricating a result.
5. THE ProofRoute_Agent SHALL reuse the existing Runtime, Guardrails, authentication, stream event contract, and observability instrumentation.
6. THE ProofRoute_Agent SHALL not create a duplicate agent, runtime, memory resource, gateway, knowledge base, table, bucket, identity provider, guardrail, or observability stack.

### Requirement 17: Managed Code Interpreter Scoring and Planning

**User Story:** As a Candidate, I want exact score and plan calculations executed through the official managed Code Interpreter, so that agent recommendations use reproducible computation rather than approximate language-model arithmetic.

#### Acceptance Criteria

1. WHEN a verified Skill_Profile and market result are available, THE ProofRoute_Agent SHALL invoke the real AgentCore_Code_Interpreter through the official Strands integration using the verified SkillForge resource configuration.
2. WHEN AgentCore_Code_Interpreter computes readiness, priorities, match counts, or an ordered action plan, THE AgentCore_Code_Interpreter SHALL execute versioned deterministic Python logic implementing the formulas and tie-break rules defined in Requirements 4, 5, and 9.
3. WHEN AgentCore_Code_Interpreter returns a result, THE ProofRoute_Agent SHALL accept only a structured result containing schema version, input digest, score, selected gap, ordered plan, market-source label, and calculation diagnostics.
4. WHEN identical verified inputs and calculation version are provided, THE AgentCore_Code_Interpreter SHALL return identical numeric scores, selected gap, and ordered plan.
5. IF the AgentCore_Code_Interpreter result violates score ranges, monotonicity, schema, input digest, or deterministic tie-break rules, THEN THE ProofRoute_Agent SHALL reject the result and preserve the previous verified state.
6. THE AgentCore_Code_Interpreter SHALL not determine Proof_Challenge pass/fail, authorize Skill_State promotion, or replace the Deterministic_Evaluator.
7. WHEN the Deterministic_Evaluator returns `passed`, THE ProofRoute_Agent SHALL use that authoritative result as the only evidence that permits promotion before requesting recalculation and replanning.
8. IF AgentCore_Code_Interpreter is unavailable, THEN THE ProofRoute_Agent SHALL use the existing deterministic local scoring and planning functions, label the calculation source as `local-fallback`, and avoid claiming managed Code Interpreter execution.

### Requirement 18: Official SkillForge Market Gateway with Local Fallback

**User Story:** As a Candidate, I want market evidence from the official SkillForge knowledge base, so that recommendations use the workshop's verified market source while remaining usable during service outages.

#### Acceptance Criteria

1. WHEN market intelligence is required and the Verification_Gate has passed, THE ProofRoute_Agent SHALL query the SkillForge_KB through the Market_Gateway_Tool configured from the SkillForge_Parameter_Manifest.
2. WHEN the Market_Gateway_Tool returns market evidence, THE ProofRoute_Agent SHALL retain source identifiers or citations supplied by the tool and label the market source as `skillforge-kb`.
3. WHEN market evidence is transformed into frequencies or job matches, THE AgentCore_Code_Interpreter SHALL use only validated structured evidence records and the deterministic formulas defined by the Skill_Profile contract.
4. IF the Verification_Gate has not passed or the Market_Gateway_Tool or SkillForge_KB is unavailable, THEN THE ProofRoute_Agent SHALL use the Local_Market_Fallback, label the market source as `local-fallback`, and include a non-secret explanation of the fallback reason.
5. THE Local_Market_Fallback SHALL preserve the existing validated canonicalization, frequency, gap, score, and monotonic matching behavior.
6. THE ProofRoute_Agent SHALL not claim that local fallback records came from AWS, SkillForge, AgentCore Gateway, or the SkillForge_KB.

### Requirement 19: Per-User Scoped Memory

**User Story:** As a Candidate, I want my ProofRoute progression isolated from other users, so that my evidence and recommendations remain scoped to my identity.

#### Acceptance Criteria

1. THE Memory_Store SHALL scope every ProofRoute read and write by the authenticated Candidate user ID, the ProofRoute namespace, and a ProofRoute session identifier.
2. WHEN the ProofRoute_Agent writes a Skill_Profile, plan, challenge outcome, or source label, THE Memory_Store SHALL include schema version, Candidate scope, UTC timestamp, and an idempotency or input-digest field.
3. WHEN the ProofRoute_Agent retrieves progression, THE Memory_Store SHALL reject records whose Candidate scope or ProofRoute namespace does not match the authenticated request.
4. IF the authenticated Candidate user ID is absent or invalid, THEN THE ProofRoute_Agent SHALL reject Memory_Store access and SHALL not substitute a shared or default actor ID.
5. WHEN Memory data is logged or traced, THE ProofRoute_Agent SHALL exclude CV text, submitted code, evidence snippets, secret values, and raw memory payloads from telemetry attributes.
6. IF Memory_Store is unavailable, THEN THE ProofRoute_Agent SHALL preserve in-request verified state, label persistence as unavailable, and avoid claiming cross-session restoration.

### Requirement 20: Security, Arabic RTL, and Observability

**User Story:** As a Candidate, I want a safe, observable, bilingual-friendly dashboard, so that ProofRoute remains trustworthy and usable in the Riyadh context.

#### Acceptance Criteria

1. THE Deterministic_Evaluator SHALL retain the existing AST allowlist, isolated temporary directory, bounded output, timeout, fail-closed transition, and deterministic hidden-mutant behavior as the authoritative challenge evaluation path.
2. THE ProofRoute_Agent SHALL pass only bounded structured scoring and planning inputs to AgentCore_Code_Interpreter and SHALL exclude AWS credentials, SSM secret values, session tokens, raw environment dumps, and unrelated user data.
3. THE ProofRoute_Dashboard SHALL provide lightweight Arabic presentation for primary headings, actions, status labels, validation messages, and result summaries without requiring a separate frontend application.
4. WHEN Arabic presentation is active, THE ProofRoute_Dashboard SHALL set the relevant content direction to `rtl`, preserve code and numeric calculation blocks as `ltr`, and render the existing workflow without horizontal scrolling at 1280px.
5. WHERE Arabic presentation is not active, THE ProofRoute_Dashboard SHALL preserve the existing English layout and behavior.
6. WHEN ProofRoute invokes AgentCore Runtime, Code Interpreter, Gateway, Memory, or the Deterministic_Evaluator, THE ProofRoute_Agent SHALL use the existing logging, tracing, correlation, and CloudWatch/OpenTelemetry paths with operation name, duration, status, source label, and non-secret resource role.
7. THE ProofRoute_Agent SHALL not place CV content, submitted code, credentials, SSM values, or raw tool payloads in logs, traces, metrics, or Candidate-visible infrastructure errors.

### Requirement 21: Shared Infrastructure Reuse and Evidence-Based Claims

**User Story:** As a system owner, I want ProofRoute to reuse verified shared infrastructure, so that the correction does not create duplicate cost, drift, or misleading AWS claims.

#### Acceptance Criteria

1. THE ProofRoute implementation SHALL reuse the verified Shared_Foundation resources identified by the SkillForge_Parameter_Manifest and existing Starter_Kit deployment.
2. WHEN infrastructure overlap is discovered, THE Verification_Gate SHALL document the overlapping stack, resource type, identifier fingerprint, ownership evidence, and recommended reuse path without deleting, replacing, importing, or modifying the resource.
3. THE ProofRoute implementation SHALL not deploy or recreate the Shared_Foundation during verification or feature integration.
4. IF a required shared resource cannot be verified, THEN THE ProofRoute implementation SHALL mark the dependent capability as blocked or use an explicitly labeled local fallback rather than create a replacement resource.
5. WHEN documentation or UI text describes an AWS-backed action, THE ProofRoute implementation SHALL make the claim only when sanitized verification or runtime evidence confirms the action occurred.
6. WHEN official SkillForge resources and illustrative user commands conflict, THE ProofRoute implementation SHALL prefer the verified official SkillForge resource and record the discrepancy without executing destructive remediation.
7. WHEN all implementation and validation tasks complete, THE implementation workflow SHALL run a credential and secret scan, full Python tests, CDK build and tests, targeted integration tests, and non-destructive smoke checks before any push.
8. IF the Verification_Gate or any required validation is blocked or fails, THEN THE implementation workflow SHALL not push changes and SHALL record the exact sanitized blocker and manual remediation commands in `docs/PROJECT_STATE.md`.
