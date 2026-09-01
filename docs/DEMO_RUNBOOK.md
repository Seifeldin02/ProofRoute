# ProofRoute Demo Runbook

## Local startup

From PowerShell at the repository root:

```powershell
$env:DEV_MODE = "true"
$env:DEV_USER_ID = "proofroute-demo-user"
$env:DEV_RELOAD = "false"
$env:AWS_REGION = "us-west-2"
$env:AWS_DEFAULT_REGION = "us-west-2"
$env:AGENTCORE_RUNTIME_ARN = "local-disabled"
$env:MEMORY_ID = "local-disabled"
$env:PROOFROUTE_STATE_ACTION_ENABLED = "false"
$env:AWS_EC2_METADATA_DISABLED = "true"

Set-Location .\chatapp
& "..\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Open **http://127.0.0.1:8080/proof**. The sample starter chat remains at `/chat`; ProofRoute is the dedicated `/proof` dashboard.

If dependencies need synchronization first:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install -r ".\chatapp\requirements.txt"
```

Do not create a committed `.env` for the local deterministic demo. If an ignored `chatapp/.env` already exists, note that the application loads it with `override=True`, so its values can override the PowerShell values above.

## AWS credentials — enter them outside this repository

Use the verified named profile `skillforge` in `us-west-2`; never paste credentials into `.env`, source code, chat, or documentation. If temporary workshop credentials expire, refresh that profile outside the repository before running AWS checks.

### Workshop uses AWS IAM Identity Center / SSO

```powershell
& "C:\Program Files\Amazon\AWSCLIV2\aws.exe" configure sso --profile skillforge
& "C:\Program Files\Amazon\AWSCLIV2\aws.exe" sso login --profile skillforge
& "C:\Program Files\Amazon\AWSCLIV2\aws.exe" sts get-caller-identity --profile skillforge --region us-west-2 --no-cli-pager
$env:AWS_PROFILE = "skillforge"
```

### Workshop supplied temporary access-key credentials

Run the interactive configuration command and enter the access key and secret only at its prompts:

```powershell
& "C:\Program Files\Amazon\AWSCLIV2\aws.exe" configure --profile skillforge
```

Use `us-west-2` as the default region and `json` as the output format. If the event also supplied a session token, place it in the named profile outside the repository using your approved credential handoff process. AWS CLI stores named credentials under `%USERPROFILE%\.aws\credentials`; do not copy that file into this repository. Then verify:

```powershell
& "C:\Program Files\Amazon\AWSCLIV2\aws.exe" sts get-caller-identity --profile skillforge --region us-west-2 --no-cli-pager
$env:AWS_PROFILE = "skillforge"
```

Only after STS succeeds should the read-only workshop resource checks or deployment be attempted.

## Reliable demo inputs

- CV: `docs/demo/demo_cv.txt`
- Known failing test: `docs/demo/failing_submission.py`
- Known passing test: `docs/demo/passing_submission.py`

## Exact demo sequence

1. Open `/proof` and paste `docs/demo/demo_cv.txt`.
2. Select **Analyze my evidence**.
3. Confirm the real calculated starting state: readiness **55%**, strong matches **4**, and highest-impact gap **Automated Testing**.
4. Paste `docs/demo/failing_submission.py` into the challenge editor and select **Run proof**.
5. Confirm `FAILED`; no skill promotion or before/after card appears, and readiness remains 55%.
6. Paste `docs/demo/passing_submission.py` and run again.
7. Confirm `PASSED`; Automated Testing becomes Demonstrated, readiness changes **55% → 73%**, and strong matches change **4 → 7**.

These values are outputs of the checked-in dataset and deterministic implementation; they are not response constants.

## Source and persistence disclosure

The local dashboard uses `chatapp/app/data/riyadh_jobs.json`, a checked-in curated Riyadh/Saudi dataset. It does not claim live SkillForge retrieval. With `PROOFROUTE_STATE_ACTION_ENABLED=false`, progression is carried in the submitted snapshot for the current flow and the UI truthfully reports AgentCore Memory persistence as unavailable.

Official SkillForge SSM parameters and the required shared resources were verified read-only in `us-west-2` with profile `skillforge`. The shared workshop stacks were not modified or recreated.

## Deployment status

The project-specific AgentCore Runtime `proofroute_agent-2czYXoGfYy` and its `DEFAULT` endpoint are `READY`; a direct runtime invocation returned exactly `PROOFROUTE_RUNTIME_OK`. Public web deployment was intentionally not attempted because the existing full CDK path would provision duplicate Foundation, Knowledge Base, Memory, Cognito, table, and related resources instead of safely reusing the shared workshop foundation. No public ProofRoute URL is available; use the verified local `/proof` flow above.
