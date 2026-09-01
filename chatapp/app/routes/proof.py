"""Authenticated FastAPI/HTMX routes for the deterministic ProofRoute MVP."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from app.agentcore.client import AgentCoreClient
from app.agentcore.memory import MemoryClient
from app.models.events import ErrorEvent, MessageEvent
from app.proof_route import (
    AUTOMATED_TESTING_CHALLENGE,
    JOBS,
    SNAPSHOT_PREFIX,
    TARGET_ROLE,
    USING_DEVELOPMENT_FALLBACK,
    ProgressSnapshot,
    SkillProfile,
    SkillState,
    apply_pass,
    compute_readiness,
    create_snapshot,
    evaluate_automated_testing,
    extract_profile,
    match_jobs,
    select_gap,
    snapshot_from_events,
    snapshot_from_message,
    snapshot_to_message,
)
from app.templates_config import TEMPLATES_DIR, templates

router = APIRouter(tags=["proof-route"])
PROOF_SESSION_ID = "proof-route-profile-v1"
PERSISTENCE_ACK = "PROOFROUTE_STATE_SAVED_V1"


def _authenticated_user(request: Request) -> tuple[str, str | None]:
    user = getattr(request.state, "user", None)
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return str(user_id), getattr(user, "email", None)


async def _request_payload(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        value = await request.json()
        return dict(value) if isinstance(value, Mapping) else {}
    form = await request.form()
    return {key: value for key, value in form.items()}


async def _retrieve_snapshot(user_id: str) -> tuple[ProgressSnapshot | None, str, str | None]:
    try:
        events = await MemoryClient().get_events(
            session_id=PROOF_SESSION_ID,
            user_id=user_id,
            max_results=50,
        )
    except Exception as exc:  # configuration/client construction can fail before get_events' safety net
        return None, "unavailable", f"Progress could not be loaded ({type(exc).__name__})."
    snapshot = snapshot_from_events(events)
    if snapshot is None:
        return None, "not_found_or_unavailable", (
            "No saved ProofRoute profile was returned. You can analyze a CV to start or continue in this request."
        )
    return snapshot, "loaded", None


def _state_action_enabled() -> bool:
    """Require explicit deployment opt-in before invoking the state-action branch.

    This prevents snapshots from being sent to the ordinary LLM path. A compatible
    agent must branch on ``PROOFROUTE_STATE_V1:`` before model construction and
    emit the exact acknowledgement ``PROOFROUTE_STATE_SAVED_V1``.
    """
    return os.environ.get("PROOFROUTE_STATE_ACTION_ENABLED", "").strip().lower() in {"1", "true", "yes"}


async def _persist_snapshot(user_id: str, snapshot: ProgressSnapshot) -> tuple[str, str | None]:
    if not _state_action_enabled():
        return "unavailable", (
            "Progress is visible for this response but was not saved: the deployed agent has not declared "
            "the compatible ProofRoute state action."
        )
    acknowledged = False
    try:
        async for event in AgentCoreClient().invoke_stream(
            prompt=snapshot_to_message(snapshot),
            session_id=PROOF_SESSION_ID,
            user_id=user_id,
        ):
            if isinstance(event, ErrorEvent):
                return "failed", f"Progress was not saved: {event.message}"
            if isinstance(event, MessageEvent) and PERSISTENCE_ACK in (event.content or ""):
                acknowledged = True
    except Exception as exc:
        return "failed", f"Progress was not saved ({type(exc).__name__})."
    if not acknowledged:
        return "failed", "Progress was not saved because the agent did not acknowledge the state action."
    return "saved", None


def _profile_context(
    request: Request,
    profile: SkillProfile | None = None,
    *,
    user_email: str | None = None,
    cv_text: str = "",
    code_submission: str = "",
    evaluation: Mapping[str, Any] | None = None,
    diff: Mapping[str, Any] | None = None,
    persistence_status: str = "not_attempted",
    persistence_warning: str | None = None,
    validation_errors: Mapping[str, str] | None = None,
    snapshot_message: str = "",
) -> dict[str, Any]:
    skill_groups = {state.value: [] for state in SkillState}
    readiness = 0
    gap_data = None
    matches_data: list[dict[str, Any]] = []
    all_matches = ()
    if profile is not None:
        readiness = compute_readiness(profile)
        for skill in profile.skills:
            skill_groups[skill.state.value].append(skill.to_dict())
        gap = select_gap(profile, JOBS)
        gap_data = gap.to_dict() if gap else None
        all_matches = match_jobs(profile, JOBS)
        matches_data = [match.to_dict() for match in all_matches[:10]]
    return {
        "request": request,
        "partial": request.headers.get("HX-Request", "").lower() == "true",
        "user_email": user_email,
        "is_admin": getattr(request.state, "is_admin", False),
        "target_role": TARGET_ROLE,
        "has_profile": profile is not None,
        "profile": profile.to_dict() if profile else None,
        "profile_data": profile.to_dict() if profile else None,
        "readiness": readiness,
        "skill_groups": skill_groups,
        "gap": gap_data,
        "gap_reason": gap_data["rationale"] if gap_data else "",
        "market_relevance": (
            {
                "frequency": gap_data["market_frequency"],
                "near_match_opportunities": gap_data["opportunity_count"],
                "priority_score": gap_data["priority_score"],
            }
            if gap_data else None
        ),
        "challenge": AUTOMATED_TESTING_CHALLENGE.to_dict(),
        "challenge_data": AUTOMATED_TESTING_CHALLENGE.to_dict(),
        "cv_text": cv_text,
        "code_submission": code_submission,
        "evaluation": dict(evaluation) if evaluation else None,
        "evaluation_data": dict(evaluation) if evaluation else None,
        "transition": dict(diff) if diff else None,
        "diff": dict(diff) if diff else None,
        "matches": matches_data,
        "strong_match_count": sum(match.matched for match in all_matches),
        "persistence_status": persistence_status,
        "persistence_warning": persistence_warning,
        "validation_errors": dict(validation_errors or {}),
        "snapshot_message": snapshot_message,
        "proof_session_id": PROOF_SESSION_ID,
        "dataset_source": "temporary_development_fallback" if USING_DEVELOPMENT_FALLBACK else "riyadh_jobs.json",
    }


def _json_safe_context(context: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in context.items() if key != "request"}


def _render(request: Request, context: dict[str, Any], status_code: int = 200) -> Response:
    """Render the teammate template when present, otherwise return testable JSON."""
    template_path = Path(TEMPLATES_DIR) / "proof.html"
    if template_path.is_file():
        return templates.TemplateResponse("proof.html", context, status_code=status_code)
    response = JSONResponse(_json_safe_context(context), status_code=status_code)
    response.headers["X-ProofRoute-Representation"] = "json-fallback"
    return response


@router.get("/proof")
async def proof_page(request: Request) -> Response:
    user_id, user_email = _authenticated_user(request)
    snapshot, status, warning = await _retrieve_snapshot(user_id)
    profile = snapshot.profile if snapshot else None
    context = _profile_context(
        request,
        profile,
        user_email=user_email,
        persistence_status=status,
        persistence_warning=warning,
        snapshot_message=snapshot_to_message(snapshot) if snapshot else "",
    )
    return _render(request, context)


@router.post("/proof/profile")
async def create_proof_profile(request: Request) -> Response:
    user_id, user_email = _authenticated_user(request)
    payload = await _request_payload(request)
    cv_text = str(payload.get("cv_text", ""))
    try:
        profile = extract_profile(cv_text, JOBS)
    except ValueError as exc:
        context = _profile_context(
            request,
            user_email=user_email,
            cv_text=cv_text,
            validation_errors={"cv_text": str(exc)},
            persistence_status="not_attempted",
        )
        return _render(request, context, status_code=422)
    snapshot = create_snapshot(profile, JOBS)
    status, warning = await _persist_snapshot(user_id, snapshot)
    context = _profile_context(
        request,
        profile,
        user_email=user_email,
        cv_text=cv_text,
        persistence_status=status,
        persistence_warning=warning,
        snapshot_message=snapshot_to_message(snapshot),
    )
    return _render(request, context)


@router.post("/proof/evaluate")
async def evaluate_proof(request: Request) -> Response:
    user_id, user_email = _authenticated_user(request)
    payload = await _request_payload(request)
    code = str(payload.get("code", payload.get("code_submission", "")))
    submitted_snapshot = snapshot_from_message(str(payload.get("snapshot_message", payload.get("snapshot", ""))))
    load_status = "submitted"
    load_warning = None
    if submitted_snapshot is None:
        submitted_snapshot, load_status, load_warning = await _retrieve_snapshot(user_id)
    if submitted_snapshot is None:
        context = _profile_context(
            request,
            user_email=user_email,
            code_submission=code,
            validation_errors={"profile": "Analyze a CV before running a proof challenge."},
            persistence_status=load_status,
            persistence_warning=load_warning,
        )
        return _render(request, context, status_code=409)

    evaluation = evaluate_automated_testing(code)
    transition = apply_pass(submitted_snapshot.profile, evaluation, JOBS)
    snapshot = create_snapshot(transition.profile, JOBS, evaluation)
    persist_status, persist_warning = await _persist_snapshot(user_id, snapshot)
    warning = persist_warning or load_warning
    context = _profile_context(
        request,
        transition.profile,
        user_email=user_email,
        code_submission=code,
        evaluation=evaluation.to_dict(),
        diff=transition.diff.to_dict() if transition.diff else None,
        persistence_status=persist_status,
        persistence_warning=warning,
        snapshot_message=snapshot_to_message(snapshot),
    )
    return _render(request, context)


__all__ = [
    "PERSISTENCE_ACK", "PROOF_SESSION_ID", "router", "create_proof_profile",
    "evaluate_proof", "proof_page",
]
