"""Focused tests for the complete deterministic ProofRoute demo loop."""

from __future__ import annotations

from html import unescape
from pathlib import Path
import re
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.proof_route import (
    JOBS,
    USING_DEVELOPMENT_FALLBACK,
    SkillState,
    apply_pass,
    compute_readiness,
    evaluate_automated_testing,
    extract_profile,
    match_jobs,
    select_gap,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "docs" / "demo"
DEMO_CV = (DEMO_DIR / "demo_cv.txt").read_text(encoding="utf-8")
FAILING_CODE = (DEMO_DIR / "failing_submission.py").read_text(encoding="utf-8")
PASSING_CODE = (DEMO_DIR / "passing_submission.py").read_text(encoding="utf-8")


def _snapshot_from_html(body: str) -> str:
    match = re.search(r'name="snapshot_message" value="([^"]+)"', body)
    assert match, "rendered response did not include the progression snapshot"
    return unescape(match.group(1))


def test_demo_fixtures_drive_real_deterministic_improvement():
    assert len(JOBS) == 12
    assert USING_DEVELOPMENT_FALLBACK is False

    profile = extract_profile(DEMO_CV, JOBS)
    gap = select_gap(profile, JOBS)
    failing = evaluate_automated_testing(FAILING_CODE)
    passing = evaluate_automated_testing(PASSING_CODE)

    before_score = compute_readiness(profile)
    before_matches = sum(match.matched for match in match_jobs(profile, JOBS))
    failed_transition = apply_pass(profile, failing, JOBS)
    passed_transition = apply_pass(profile, passing, JOBS)
    after_score = compute_readiness(passed_transition.profile)
    after_matches = sum(match.matched for match in match_jobs(passed_transition.profile, JOBS))

    assert gap is not None and gap.skill_name == "Automated Testing"
    assert failing.status == "failed"
    assert failed_transition.diff is None
    assert failed_transition.profile == profile
    assert passing.status == "passed"
    assert passed_transition.diff is not None
    assert before_score == 55
    assert after_score == 73
    assert before_matches == 4
    assert after_matches == 7
    assert after_score > before_score
    assert after_matches > before_matches
    assert next(
        skill.state
        for skill in passed_transition.profile.skills
        if skill.name == "Automated Testing"
    ) is SkillState.DEMONSTRATED


def test_dedicated_frontend_and_htmx_demo_flow(monkeypatch):
    env = {
        "DEV_MODE": "true",
        "DEV_USER_ID": "proofroute-demo-user",
        "DEV_RELOAD": "false",
        "AWS_REGION": "us-west-2",
        "AWS_DEFAULT_REGION": "us-west-2",
        "AGENTCORE_RUNTIME_ARN": "local-disabled",
        "MEMORY_ID": "local-disabled",
        "PROOFROUTE_STATE_ACTION_ENABLED": "false",
        "AWS_EC2_METADATA_DISABLED": "true",
    }
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    from app.config import get_config
    from app.main import app

    get_config.cache_clear()
    with patch("app.routes.proof.MemoryClient.get_events", new=AsyncMock(return_value=[])):
        with TestClient(app) as client:
            page = client.get("/proof")
            assert page.status_code == 200
            assert page.headers["content-type"].startswith("text/html")
            assert "ProofRoute" in page.text
            assert "Analyze my evidence" in page.text
            assert "X-ProofRoute-Representation" not in page.headers

            profile_response = client.post(
                "/proof/profile",
                json={"cv_text": DEMO_CV},
                headers={"HX-Request": "true"},
            )
            assert profile_response.status_code == 200
            assert profile_response.text.lstrip().startswith('<main id="proof-content"')
            assert "<html" not in profile_response.text
            assert "55%" in profile_response.text
            assert "Automated Testing" in profile_response.text
            assert "Demonstrated" in profile_response.text
            assert "Unverified" in profile_response.text
            assert "Missing" in profile_response.text
            assert "Curated Riyadh roles" in profile_response.text

            failed_response = client.post(
                "/proof/evaluate",
                json={
                    "code": FAILING_CODE,
                    "snapshot_message": _snapshot_from_html(profile_response.text),
                },
                headers={"HX-Request": "true"},
            )
            assert failed_response.status_code == 200
            assert "FAILED" in failed_response.text
            assert "Your proof changed the route" not in failed_response.text
            assert "55%" in failed_response.text

            passed_response = client.post(
                "/proof/evaluate",
                json={
                    "code": PASSING_CODE,
                    "snapshot_message": _snapshot_from_html(failed_response.text),
                },
                headers={"HX-Request": "true"},
            )
            assert passed_response.status_code == 200
            assert "PASSED" in passed_response.text
            assert "Your proof changed the route" in passed_response.text
            assert "55%" in passed_response.text
            assert "73%" in passed_response.text
            assert ">4<" in passed_response.text
            assert ">7<" in passed_response.text

    get_config.cache_clear()
