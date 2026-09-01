"""Deterministic domain logic for the ProofRoute backend MVP.

No LLM participates in extraction, scoring, matching, challenge evaluation, or
promotion. The bundled job records are a temporary development fallback only;
a valid ``app/data/riyadh_jobs.json`` is preferred automatically.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

TARGET_ROLE = "Junior Backend Engineer — Riyadh"
SNAPSHOT_PREFIX = "PROOFROUTE_STATE_V1:"
SNAPSHOT_SCHEMA_VERSION = 1
MATCH_THRESHOLD = 0.60
MIN_CV_LENGTH = 50
MAX_CV_LENGTH = 10_000
MAX_CODE_LENGTH = 10_000
JOBS_PATH = Path(__file__).resolve().parent / "data" / "riyadh_jobs.json"


class SkillState(str, Enum):
    DEMONSTRATED = "Demonstrated"
    UNVERIFIED = "Unverified"
    MISSING = "Missing"


@dataclass(frozen=True)
class SkillRecord:
    name: str
    state: SkillState
    market_frequency: int | None
    priority_score: float = 0.0
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "market_frequency": self.market_frequency,
            "priority_score": self.priority_score,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SkillRecord":
        name = str(value.get("name", "")).strip()
        if not name:
            raise ValueError("skill name is required")
        state = SkillState(value.get("state"))
        frequency = value.get("market_frequency")
        if frequency is not None and (type(frequency) is not int or not 0 <= frequency <= 100):
            raise ValueError("market_frequency must be an integer from 0 to 100")
        priority = value.get("priority_score", 0.0)
        if not isinstance(priority, (int, float)) or isinstance(priority, bool):
            raise ValueError("priority_score must be numeric")
        evidence = str(value.get("evidence", ""))[:300]
        return cls(name, state, frequency, float(priority), evidence)


@dataclass(frozen=True)
class Job:
    id: str
    title: str
    location: str
    required_skills: tuple[str, ...]
    company: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "location": self.location,
            "required_skills": list(self.required_skills),
            "company": self.company,
        }


@dataclass(frozen=True)
class SkillProfile:
    target_role: str
    skills: tuple[SkillRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"target_role": self.target_role, "skills": [skill.to_dict() for skill in self.skills]}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SkillProfile":
        role = str(value.get("target_role", "")).strip()
        raw_skills = value.get("skills")
        if not role or not isinstance(raw_skills, list):
            raise ValueError("profile target_role and skills are required")
        skills = tuple(SkillRecord.from_dict(item) for item in raw_skills if isinstance(item, Mapping))
        if len(skills) != len(raw_skills):
            raise ValueError("invalid skill record")
        names = [skill.name.casefold() for skill in skills]
        if len(names) != len(set(names)):
            raise ValueError("duplicate canonical skills")
        return cls(role, skills)


CandidateProfile = SkillProfile


@dataclass(frozen=True)
class GapSelection:
    skill_name: str
    state: SkillState
    market_frequency: int
    priority_score: float
    opportunity_count: int
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "state": self.state.value,
            "market_frequency": self.market_frequency,
            "priority_score": self.priority_score,
            "opportunity_count": self.opportunity_count,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class JobMatch:
    job_id: str
    title: str
    coverage: float
    matched: bool
    required_skills: tuple[str, ...]
    company: str = ""
    location: str = ""
    matched_skills: tuple[str, ...] = ()
    unverified_skills: tuple[str, ...] = ()
    missing_skills: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "title": self.title,
            "coverage": self.coverage,
            "matched": self.matched,
            "required_skills": list(self.required_skills),
            "company": self.company,
            "location": self.location,
            "matched_skills": list(self.matched_skills),
            "unverified_skills": list(self.unverified_skills),
            "missing_skills": list(self.missing_skills),
        }


@dataclass(frozen=True)
class ChallengeDefinition:
    title: str
    skill: str
    statement: str
    signature: str
    criteria: tuple[str, ...]
    examples: tuple[Mapping[str, str], ...]
    starter_code: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "skill": self.skill,
            "statement": self.statement,
            "signature": self.signature,
            "criteria": list(self.criteria),
            "examples": [dict(example) for example in self.examples],
            "starter_code": self.starter_code,
        }


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


TestCaseResult = CheckResult


@dataclass(frozen=True)
class EvaluationResult:
    status: str
    skill_name: str
    cases: tuple[CheckResult, ...]
    hint: str
    stdout: str
    stderr: str
    outcome_id: str
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "skill_name": self.skill_name,
            "cases": [case.to_dict() for case in self.cases],
            "hint": self.hint,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "outcome_id": self.outcome_id,
            "error": self.error,
        }


@dataclass(frozen=True)
class TransitionDiff:
    previous_score: int
    new_score: int
    score_delta: int
    previous_match_count: int
    new_match_count: int
    demonstrated_skill: str
    newly_matched_jobs: tuple[str, ...]
    improved_jobs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "previous_score": self.previous_score,
            "new_score": self.new_score,
            "score_delta": self.score_delta,
            "previous_match_count": self.previous_match_count,
            "new_match_count": self.new_match_count,
            "demonstrated_skill": self.demonstrated_skill,
            "newly_matched_jobs": list(self.newly_matched_jobs),
            "improved_jobs": list(self.improved_jobs),
        }


@dataclass(frozen=True)
class TransitionResult:
    profile: SkillProfile
    evaluation: EvaluationResult
    diff: TransitionDiff | None

    @property
    def promoted(self) -> bool:
        return self.diff is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "evaluation": self.evaluation.to_dict(),
            "diff": self.diff.to_dict() if self.diff else None,
            "promoted": self.promoted,
        }


@dataclass(frozen=True)
class ProgressSnapshot:
    target_role: str
    skills: tuple[SkillRecord, ...]
    completed_challenge: Mapping[str, str] | None
    latest_score: int
    latest_match_count: int
    updated_at: str
    schema_version: int = SNAPSHOT_SCHEMA_VERSION

    @property
    def profile(self) -> SkillProfile:
        return SkillProfile(self.target_role, self.skills)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "target_role": self.target_role,
            "skills": [skill.to_dict() for skill in self.skills],
            "completed_challenge": dict(self.completed_challenge) if self.completed_challenge else None,
            "latest_score": self.latest_score,
            "latest_match_count": self.latest_match_count,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProgressSnapshot":
        if value.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("unsupported snapshot schema")
        profile = SkillProfile.from_dict(value)
        score = value.get("latest_score")
        match_count = value.get("latest_match_count")
        updated_at = str(value.get("updated_at", "")).strip()
        if type(score) is not int or not 0 <= score <= 100:
            raise ValueError("invalid latest_score")
        if type(match_count) is not int or match_count < 0:
            raise ValueError("invalid latest_match_count")
        if not updated_at:
            raise ValueError("updated_at is required")
        completed = value.get("completed_challenge")
        if completed is not None:
            if not isinstance(completed, Mapping):
                raise ValueError("invalid completed_challenge")
            required = ("outcome_id", "skill_name", "status", "updated_at")
            completed = {key: str(completed.get(key, "")).strip() for key in required}
            if not all(completed.values()):
                raise ValueError("incomplete completed_challenge")
        return cls(
            profile.target_role,
            profile.skills,
            completed,
            score,
            match_count,
            updated_at,
        )


_SYNONYMS: dict[str, tuple[str, ...]] = {
    "Automated Testing": ("automated testing", "unit testing", "unit tests", "pytest", "test automation"),
    "AWS": ("aws", "amazon web services"),
    "CI/CD": ("ci/cd", "continuous integration", "continuous delivery"),
    "Data Structures": ("data structures", "algorithms"),
    "Docker": ("docker", "containers", "containerization"),
    "FastAPI": ("fastapi",),
    "Git": ("git", "github", "version control"),
    "Linux": ("linux", "unix"),
    "Python": ("python", "python 3"),
    "REST APIs": ("rest api", "rest apis", "restful api", "api development"),
    "SQL": ("sql", "postgresql", "postgres", "mysql", "relational database"),
}


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    escaped = re.escape(phrase.strip()).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)


_SYNONYM_PATTERNS = {
    canonical: tuple(_phrase_pattern(phrase) for phrase in phrases)
    for canonical, phrases in _SYNONYMS.items()
}
_SYNONYM_LOOKUP = {
    re.sub(r"\s+", " ", phrase.strip()).casefold(): canonical
    for canonical, phrases in _SYNONYMS.items()
    for phrase in (canonical, *phrases)
}


def canonicalize_skill(value: str) -> str:
    normalized = re.sub(r"\s+", " ", str(value).strip())
    if not normalized:
        raise ValueError("skill cannot be empty")
    return _SYNONYM_LOOKUP.get(normalized.casefold(), normalized.title())


# TEMPORARY DEVELOPMENT FALLBACK: replaced automatically by any valid JSON dataset.
_DEVELOPMENT_FALLBACK_JOBS: tuple[Job, ...] = (
    Job("dev-01", "Junior Python Backend Engineer", "Riyadh", ("Python", "REST APIs", "SQL", "Git", "Automated Testing")),
    Job("dev-02", "Backend Software Engineer", "Riyadh", ("Python", "FastAPI", "SQL", "Docker", "Automated Testing")),
    Job("dev-03", "Graduate Software Engineer", "Saudi Arabia", ("Python", "Data Structures", "Git", "Linux")),
    Job("dev-04", "Junior Cloud Backend Developer", "Riyadh", ("Python", "AWS", "REST APIs", "Docker", "CI/CD")),
    Job("dev-05", "Associate API Engineer", "Riyadh", ("REST APIs", "SQL", "Git", "Automated Testing")),
    Job("dev-06", "Junior Platform Engineer", "Saudi Arabia", ("Linux", "Docker", "AWS", "CI/CD", "Git")),
)


def _job_from_mapping(value: Mapping[str, Any]) -> Job | None:
    identifier = value.get("id")
    title = value.get("title")
    location = value.get("location")
    raw_skills = value.get("required_skills", value.get("skills"))
    if not all(isinstance(item, str) and item.strip() for item in (identifier, title, location)):
        return None
    if not isinstance(raw_skills, list) or not raw_skills:
        return None
    try:
        skills = tuple(sorted({canonicalize_skill(skill) for skill in raw_skills if isinstance(skill, str) and skill.strip()}, key=str.casefold))
    except ValueError:
        return None
    if not skills:
        return None
    raw_company = value.get("company", "")
    company = raw_company.strip() if isinstance(raw_company, str) else ""
    return Job(identifier.strip(), title.strip(), location.strip(), skills, company)


def load_jobs(path: str | Path = JOBS_PATH) -> tuple[Job, ...]:
    """Load, validate, canonicalize, deduplicate, and deterministically sort jobs.

    Malformed records are skipped. A missing, malformed, or effectively empty
    dataset falls back to the small in-module development fixture.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(raw, Mapping):
            raw = raw.get("jobs")
        if not isinstance(raw, list):
            raise ValueError("job dataset must be a list")
        by_id: dict[str, Job] = {}
        for item in raw:
            if isinstance(item, Mapping):
                job = _job_from_mapping(item)
                if job is not None and job.id not in by_id:
                    by_id[job.id] = job
        if not by_id:
            raise ValueError("job dataset has no valid records")
        return tuple(sorted(by_id.values(), key=lambda job: (job.title.casefold(), job.id.casefold())))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return tuple(sorted(_DEVELOPMENT_FALLBACK_JOBS, key=lambda job: (job.title.casefold(), job.id.casefold())))


JOBS = load_jobs()
USING_DEVELOPMENT_FALLBACK = not JOBS_PATH.exists() or JOBS == tuple(
    sorted(_DEVELOPMENT_FALLBACK_JOBS, key=lambda job: (job.title.casefold(), job.id.casefold()))
)


def compute_market_frequencies(jobs: Sequence[Job]) -> dict[str, int]:
    if not jobs:
        return {}
    all_skills = sorted({skill for job in jobs for skill in job.required_skills}, key=str.casefold)
    return {
        skill: round(100 * sum(skill in job.required_skills for job in jobs) / len(jobs))
        for skill in all_skills
    }


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|[\r\n]+")
_EVIDENCE_MARKER = re.compile(
    r"https?://|github\.com|\b(project|built|developed|implemented|led|deployed|created|designed|"
    r"certified|certification|engineer at|developer at)\b|\b\d+(?:\.\d+)?\s*(?:%|users?|requests?|"
    r"months?|years?|seconds?|x)\b",
    re.IGNORECASE,
)


def _sentences(cv_text: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in _SENTENCE_SPLIT.split(cv_text) if part.strip())


def extract_profile(
    cv_text: str,
    jobs: Sequence[Job] = JOBS,
    target_role: str = TARGET_ROLE,
) -> SkillProfile:
    """Extract a deterministic, canonical, evidence-aware profile from CV text."""
    if not isinstance(cv_text, str) or not MIN_CV_LENGTH <= len(cv_text) <= MAX_CV_LENGTH:
        raise ValueError(f"CV text must contain between {MIN_CV_LENGTH} and {MAX_CV_LENGTH} characters")
    frequencies = compute_market_frequencies(jobs)
    extracted: dict[str, SkillRecord] = {}
    for sentence in _sentences(cv_text):
        for canonical, patterns in _SYNONYM_PATTERNS.items():
            if any(pattern.search(sentence) for pattern in patterns):
                demonstrated = bool(_EVIDENCE_MARKER.search(sentence))
                state = SkillState.DEMONSTRATED if demonstrated else SkillState.UNVERIFIED
                evidence = sentence[:300]
                previous = extracted.get(canonical)
                if previous is None or (previous.state is SkillState.UNVERIFIED and demonstrated):
                    extracted[canonical] = SkillRecord(canonical, state, frequencies.get(canonical, 0), 0.0, evidence)
    if not extracted:
        raise ValueError("No supported skills were found; include specific skills or project experience")
    for skill, frequency in frequencies.items():
        if frequency >= 40 and skill not in extracted:
            extracted[skill] = SkillRecord(skill, SkillState.MISSING, frequency, 0.0, "")
    return SkillProfile(target_role, tuple(sorted(extracted.values(), key=lambda skill: skill.name.casefold())))


def compute_readiness(profile: SkillProfile) -> int:
    weighted = [skill for skill in profile.skills if (skill.market_frequency or 0) > 0]
    denominator = sum(skill.market_frequency or 0 for skill in weighted)
    if denominator == 0:
        return 0
    numerator = sum(
        skill.market_frequency or 0
        for skill in weighted
        if skill.state is SkillState.DEMONSTRATED
    )
    return max(0, min(100, round(100 * numerator / denominator)))


def match_jobs(profile: SkillProfile, jobs: Sequence[Job] = JOBS) -> tuple[JobMatch, ...]:
    demonstrated = {skill.name for skill in profile.skills if skill.state is SkillState.DEMONSTRATED}
    unverified = {skill.name for skill in profile.skills if skill.state is SkillState.UNVERIFIED}
    matches = []
    for job in jobs:
        matched_skills = tuple(skill for skill in job.required_skills if skill in demonstrated)
        unverified_skills = tuple(skill for skill in job.required_skills if skill in unverified)
        missing_skills = tuple(
            skill for skill in job.required_skills
            if skill not in demonstrated and skill not in unverified
        )
        coverage = len(matched_skills) / len(job.required_skills)
        matches.append(
            JobMatch(
                job.id,
                job.title,
                coverage,
                coverage >= MATCH_THRESHOLD,
                job.required_skills,
                job.company,
                job.location,
                matched_skills,
                unverified_skills,
                missing_skills,
            )
        )
    return tuple(sorted(matches, key=lambda item: (-item.coverage, item.title.casefold(), item.job_id.casefold())))


def _unlock_opportunities(profile: SkillProfile, skill_name: str, jobs: Sequence[Job]) -> int:
    demonstrated = {skill.name for skill in profile.skills if skill.state is SkillState.DEMONSTRATED}
    opportunities = 0
    for job in jobs:
        if skill_name not in job.required_skills:
            continue
        before = len(demonstrated.intersection(job.required_skills)) / len(job.required_skills)
        after = len((demonstrated | {skill_name}).intersection(job.required_skills)) / len(job.required_skills)
        if before < MATCH_THRESHOLD and (after >= MATCH_THRESHOLD or before >= 0.40):
            opportunities += 1
    return opportunities


def select_gap(profile: SkillProfile, jobs: Sequence[Job] = JOBS) -> GapSelection | None:
    """Select the highest-impact gap using a transparent deterministic formula.

    ``base = frequency * (1.0 if Missing else 0.7)`` preserves the requirement
    weighting. Candidate-near-match opportunities add three points each, capped
    at 15. The one challenge-supported skill, Automated Testing, receives only a
    1.03 feasibility multiplier. The final score is capped at 100, so support can
    break close calls but can never force that skill to win irrespective of data.
    Ties are resolved by ascending canonical skill name.
    """
    candidates: list[GapSelection] = []
    for skill in profile.skills:
        if skill.state is SkillState.DEMONSTRATED or skill.market_frequency is None:
            continue
        multiplier = 1.0 if skill.state is SkillState.MISSING else 0.7
        opportunities = _unlock_opportunities(profile, skill.name, jobs)
        feasibility = 1.03 if skill.name == "Automated Testing" else 1.0
        priority = round(min(100.0, (skill.market_frequency * multiplier + min(15, opportunities * 3)) * feasibility), 2)
        rationale = (
            f"{skill.market_frequency}% market frequency × {multiplier:.1f} {skill.state.value.lower()} weight"
            f" + {opportunities} near-match opportunit{'y' if opportunities == 1 else 'ies'}"
            f"{' × 1.03 challenge feasibility' if feasibility > 1 else ''}."
        )
        candidates.append(GapSelection(skill.name, skill.state, skill.market_frequency, priority, opportunities, rationale))
    return min(candidates, key=lambda item: (-item.priority_score, item.skill_name.casefold(), item.skill_name)) if candidates else None


AUTOMATED_TESTING_CHALLENGE = ChallengeDefinition(
    title="Prove Automated Testing: normalize_status",
    skill="Automated Testing",
    statement=(
        "Write one Python test function that verifies the supplied normalize_status callable. "
        "Your assertions must accept the correct implementation and reject implementations that omit trimming, "
        "omit lowercasing, map statuses incorrectly, or accept non-string values."
    ),
    signature="def test_normalize_status(normalize_status):",
    criteria=(
        "Trim surrounding whitespace and lowercase text.",
        "Map 'ok' to 'passed' and 'error' to 'failed'.",
        "Reject non-string inputs with TypeError.",
        "Accept the correct implementation and reject every hidden mutant.",
    ),
    examples=(
        {"input": "' OK '", "expected": "'passed'"},
        {"input": "'Error'", "expected": "'failed'"},
        {"input": "123", "expected": "TypeError"},
    ),
    starter_code=(
        "def test_normalize_status(normalize_status):\n"
        "    assert normalize_status(\" OK \") == \"passed\"\n"
        "    # Add assertions for lowercase, error mapping, and non-string rejection.\n"
    ),
)

_ALLOWED_NODES = (
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Assert, ast.Call, ast.Name,
    ast.Constant, ast.Compare, ast.BoolOp, ast.UnaryOp, ast.Try, ast.ExceptHandler,
    ast.Pass, ast.Raise, ast.Expr, ast.Load, ast.Eq, ast.NotEq, ast.Is, ast.IsNot,
    ast.In, ast.NotIn, ast.And, ast.Or, ast.Not,
)
_ALLOWED_NAMES = {"normalize_status", "TypeError", "ValueError", "AssertionError"}


def _validate_candidate_source(source: str) -> ast.Module:
    if not isinstance(source, str) or not 1 <= len(source) <= MAX_CODE_LENGTH:
        raise ValueError(f"Code must contain between 1 and {MAX_CODE_LENGTH} characters")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(f"Syntax error on line {exc.lineno}: {exc.msg}") from exc
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError("Submit exactly one function named test_normalize_status")
    function = tree.body[0]
    args = function.args
    if function.name != "test_normalize_status" or function.decorator_list:
        raise ValueError("Function must be named test_normalize_status and have no decorators")
    if (
        len(args.args) != 1 or args.args[0].arg != "normalize_status" or args.posonlyargs
        or args.kwonlyargs or args.vararg or args.kwarg or args.defaults or args.kw_defaults
    ):
        raise ValueError("test_normalize_status must accept exactly one argument named normalize_status")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"Unsupported or unsafe syntax: {type(node).__name__}")
        if isinstance(node, ast.Name):
            if "__" in node.id or node.id not in _ALLOWED_NAMES:
                raise ValueError(f"Unsupported name: {node.id}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in {"normalize_status", "AssertionError"}:
                raise ValueError("Only calls to normalize_status are allowed")
            if node.keywords:
                raise ValueError("Keyword arguments are not allowed")
        if isinstance(node, ast.Raise) and node.exc is not None:
            if not isinstance(node.exc, ast.Call) or not isinstance(node.exc.func, ast.Name) or node.exc.func.id != "AssertionError":
                raise ValueError("Only AssertionError may be raised explicitly")
    return tree


_HARNESS = r'''
import json


def correct(value):
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    normalized = value.strip().lower()
    return {"ok": "passed", "error": "failed"}.get(normalized, normalized)


def no_trim(value):
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    normalized = value.lower()
    return {"ok": "passed", "error": "failed"}.get(normalized, normalized)


def no_lowercase(value):
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    normalized = value.strip()
    return {"ok": "passed", "error": "failed"}.get(normalized, normalized)


def wrong_mapping(value):
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    normalized = value.strip().lower()
    return {"ok": "success", "error": "error"}.get(normalized, normalized)


def no_type_rejection(value):
    normalized = str(value).strip().lower()
    return {"ok": "passed", "error": "failed"}.get(normalized, normalized)


implementations = [
    ("correct", correct),
    ("no_trim", no_trim),
    ("no_lowercase", no_lowercase),
    ("wrong_mapping", wrong_mapping),
    ("no_type_rejection", no_type_rejection),
]
results = []
for name, implementation in implementations:
    try:
        test_normalize_status(implementation)
        results.append({"name": name, "accepted": True, "exception": ""})
    except BaseException as exc:
        results.append({"name": name, "accepted": False, "exception": type(exc).__name__})
print(json.dumps(results, sort_keys=True, separators=(",", ":")))
'''


def _evaluation_id(source: str, cases: Sequence[CheckResult], status: str) -> str:
    material = source + status + json.dumps([case.to_dict() for case in cases], sort_keys=True)
    return "eval-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _rejected_evaluation(source: str, message: str, status: str = "failed") -> EvaluationResult:
    outcome = _evaluation_id(source if isinstance(source, str) else "", (), status)
    return EvaluationResult(status, "Automated Testing", (), message, "", "", outcome, message)


def evaluate_automated_testing(source: str) -> EvaluationResult:
    """Evaluate one AST-constrained test function against fixed hidden mutants."""
    try:
        _validate_candidate_source(source)
    except ValueError as exc:
        return _rejected_evaluation(source, str(exc))

    stdout = ""
    stderr = ""
    try:
        with tempfile.TemporaryDirectory(prefix="proofroute-") as directory:
            workdir = Path(directory)
            try:
                os.chmod(workdir, 0o700)
            except OSError:
                pass
            runner = workdir / "runner.py"
            runner.write_text(source.rstrip() + "\n\n" + _HARNESS, encoding="utf-8")
            try:
                os.chmod(runner, 0o600)
            except OSError:
                pass
            completed = subprocess.run(
                [sys.executable, "-I", str(runner)],
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
                env={"PYTHONIOENCODING": "utf-8"},
            )
            stdout = completed.stdout[:10_000]
            stderr = completed.stderr[:10_000]
            if completed.returncode != 0:
                message = "The constrained evaluator exited with an error."
                outcome = _evaluation_id(source, (), "error")
                return EvaluationResult("error", "Automated Testing", (), message, stdout, stderr, outcome, message)
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or "")[:10_000] if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "")[:10_000] if isinstance(exc.stderr, str) else ""
        cases = tuple(CheckResult(name, "timeout", "Evaluation exceeded the 3-second limit") for name in ("correct", "no_trim", "no_lowercase", "wrong_mapping", "no_type_rejection"))
        return EvaluationResult("failed", "Automated Testing", cases, "The submitted test timed out.", stdout, stderr, _evaluation_id(source, cases, "failed"), "Evaluation timed out")
    except (OSError, subprocess.SubprocessError) as exc:
        message = f"Evaluator infrastructure failure: {type(exc).__name__}"
        return EvaluationResult("error", "Automated Testing", (), message, stdout, stderr, _evaluation_id(source, (), "error"), message)

    try:
        raw_results = json.loads(stdout.strip().splitlines()[-1])
        if not isinstance(raw_results, list) or len(raw_results) != 5:
            raise ValueError("unexpected harness output")
        cases = []
        for item in raw_results:
            name = str(item["name"])
            accepted = item["accepted"] is True
            expected_acceptance = name == "correct"
            passed = accepted == expected_acceptance
            detail = (
                "Correct implementation accepted" if name == "correct" and passed
                else "Correct implementation was rejected"
                if name == "correct"
                else "Hidden mutant rejected"
                if passed
                else "Hidden mutant was not detected"
            )
            if item.get("exception"):
                detail += f" ({item['exception']})"
            cases.append(CheckResult(name, "passed" if passed else "failed", detail))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, IndexError):
        message = "Evaluator returned malformed output."
        return EvaluationResult("error", "Automated Testing", (), message, stdout, stderr, _evaluation_id(source, (), "error"), message)

    cases_tuple = tuple(cases)
    passed = all(case.status == "passed" for case in cases_tuple)
    first_failure = next((case for case in cases_tuple if case.status != "passed"), None)
    hint = "All hidden behaviors were detected." if passed else (
        f"Strengthen the test for {first_failure.name.replace('_', ' ')}: {first_failure.detail}."
    )
    status = "passed" if passed else "failed"
    return EvaluationResult(status, "Automated Testing", cases_tuple, hint, stdout, stderr, _evaluation_id(source, cases_tuple, status))


def apply_pass(
    profile: SkillProfile,
    evaluation: EvaluationResult,
    jobs: Sequence[Job] = JOBS,
) -> TransitionResult:
    """Promote only Automated Testing backed by a passing evaluator result."""
    if evaluation.status != "passed" or evaluation.skill_name != "Automated Testing":
        return TransitionResult(profile, evaluation, None)
    index = next((i for i, skill in enumerate(profile.skills) if skill.name == "Automated Testing"), None)
    if index is None or profile.skills[index].state is SkillState.DEMONSTRATED:
        return TransitionResult(profile, evaluation, None)
    before_score = compute_readiness(profile)
    before_matches = match_jobs(profile, jobs)
    updated_skills = list(profile.skills)
    updated_skills[index] = replace(
        updated_skills[index],
        state=SkillState.DEMONSTRATED,
        evidence=evaluation.outcome_id,
        priority_score=0.0,
    )
    updated = SkillProfile(profile.target_role, tuple(updated_skills))
    after_score = compute_readiness(updated)
    after_matches = match_jobs(updated, jobs)
    before_by_id = {match.job_id: match for match in before_matches}
    newly_matched = tuple(
        match.title for match in after_matches
        if match.matched and not before_by_id[match.job_id].matched
    )
    improved = tuple(
        match.title for match in after_matches
        if match.coverage > before_by_id[match.job_id].coverage
    )
    previous_count = sum(match.matched for match in before_matches)
    new_count = sum(match.matched for match in after_matches)
    if after_score < before_score or new_count < previous_count:
        raise RuntimeError("promotion violated monotonic scoring invariants")
    diff = TransitionDiff(
        before_score,
        after_score,
        after_score - before_score,
        previous_count,
        new_count,
        "Automated Testing",
        newly_matched,
        improved,
    )
    return TransitionResult(updated, evaluation, diff)


def create_snapshot(
    profile: SkillProfile,
    jobs: Sequence[Job] = JOBS,
    evaluation: EvaluationResult | None = None,
    updated_at: str | None = None,
) -> ProgressSnapshot:
    timestamp = updated_at or datetime.now(timezone.utc).isoformat()
    completed = None
    if evaluation is not None:
        completed = {
            "outcome_id": evaluation.outcome_id,
            "skill_name": evaluation.skill_name,
            "status": evaluation.status,
            "updated_at": timestamp,
        }
    return ProgressSnapshot(
        profile.target_role,
        profile.skills,
        completed,
        compute_readiness(profile),
        sum(match.matched for match in match_jobs(profile, jobs)),
        timestamp,
    )


def snapshot_to_message(snapshot: ProgressSnapshot) -> str:
    return SNAPSHOT_PREFIX + json.dumps(snapshot.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def snapshot_from_message(message: str) -> ProgressSnapshot | None:
    if not isinstance(message, str) or not message.startswith(SNAPSHOT_PREFIX) or len(message) > 100_000:
        return None
    try:
        value = json.loads(message[len(SNAPSHOT_PREFIX):])
        return ProgressSnapshot.from_dict(value) if isinstance(value, Mapping) else None
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def _event_text_and_timestamp(event: Any) -> tuple[str | None, str]:
    if hasattr(event, "content"):
        return getattr(event, "content", None), str(getattr(event, "timestamp", ""))
    if not isinstance(event, Mapping):
        return None, ""
    timestamp = str(event.get("timestamp") or event.get("eventTimestamp") or "")
    content = event.get("content")
    if isinstance(content, str):
        return content, timestamp
    if isinstance(content, Mapping) and isinstance(content.get("text"), str):
        return content["text"], timestamp
    message = event.get("message")
    if isinstance(message, str):
        return message, timestamp
    if isinstance(message, Mapping):
        nested = message.get("content")
        if isinstance(nested, str):
            return nested, timestamp
        if isinstance(nested, list):
            for block in nested:
                if isinstance(block, Mapping) and isinstance(block.get("text"), str):
                    return block["text"], timestamp
    payload = event.get("payload")
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, Mapping):
                continue
            conversational = item.get("conversational")
            if isinstance(conversational, Mapping):
                nested = conversational.get("content")
                if isinstance(nested, Mapping) and isinstance(nested.get("text"), str):
                    return nested["text"], timestamp
    return None, timestamp


def snapshot_from_events(events: Iterable[Any]) -> ProgressSnapshot | None:
    """Return the newest valid snapshot while ignoring unrelated/malformed events."""
    candidates = []
    for index, event in enumerate(events or ()):
        text, timestamp = _event_text_and_timestamp(event)
        candidates.append((timestamp, index, text))
    for _, _, text in sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True):
        snapshot = snapshot_from_message(text) if text else None
        if snapshot is not None:
            return snapshot
    return None


__all__ = [
    "AUTOMATED_TESTING_CHALLENGE", "CandidateProfile", "ChallengeDefinition", "CheckResult",
    "EvaluationResult", "GapSelection", "JOBS", "JOBS_PATH", "Job", "JobMatch",
    "MATCH_THRESHOLD", "ProgressSnapshot", "SNAPSHOT_PREFIX", "SkillProfile", "SkillRecord",
    "SkillState", "TARGET_ROLE", "TestCaseResult", "TransitionDiff", "TransitionResult",
    "USING_DEVELOPMENT_FALLBACK", "apply_pass", "canonicalize_skill", "compute_market_frequencies",
    "compute_readiness", "create_snapshot", "evaluate_automated_testing", "extract_profile",
    "load_jobs", "match_jobs", "select_gap", "snapshot_from_events", "snapshot_from_message",
    "snapshot_to_message",
]
