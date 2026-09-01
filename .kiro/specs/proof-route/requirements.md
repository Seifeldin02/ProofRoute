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

---

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

