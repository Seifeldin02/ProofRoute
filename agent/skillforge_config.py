"""Typed, fail-closed SkillForge configuration resolved from SSM.

The checked-in manifest is intentionally name-only: it may contain SSM parameter
paths and logical roles, but never resolved values. Authoritative paths must be
discovered from the SkillForge ``/app/workshop`` inventory before a manifest is
created.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import re
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlparse


SKILLFORGE_REGION = "us-west-2"
MANIFEST_SCHEMA_VERSION = 1
_PARAMETER_PATH = re.compile(r"^/app/workshop/[A-Za-z0-9_.\-/]+$")
_CODE_INTERPRETER_ID = re.compile(
    r"^(?:aws\.codeinterpreter\.v1|[A-Za-z][A-Za-z0-9_]{0,47}-[A-Za-z0-9]{10})$"
)
_GATEWAY_ID = re.compile(r"^(?:[0-9a-z]-?){1,100}-[0-9a-z]{10}$")
_KNOWLEDGE_BASE_ID = re.compile(r"^[0-9A-Za-z]{10}$")
_MEMORY_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,99}-[A-Za-z0-9]{10}$")
_DYNAMODB_TABLE_NAME = re.compile(r"^[A-Za-z0-9_.-]{3,255}$")
_S3_BUCKET_NAME = re.compile(
    r"^(?!xn--)(?!sthree-)(?!amzn-s3-demo-)(?!.*(?:--ol-s3|\.mrap|--x-s3|--table-s3)$)"
    r"(?!\d{1,3}(?:\.\d{1,3}){3}$)(?!.*\.\.)(?!.*\.-)(?!.*-\.)"
    r"[a-z0-9](?:[a-z0-9.-]{1,61}[a-z0-9])$"
)


class SkillForgeRole(str, Enum):
    """The seven required logical roles in a SkillForge parameter manifest."""

    CODE_INTERPRETER = "code_interpreter"
    GATEWAY = "gateway"
    KNOWLEDGE_BASE = "knowledge_base"
    MEMORY = "memory"
    PROFILE_TABLE = "profile_table"
    PROGRESSION_TABLE = "progression_table"
    MARKET_BUCKET = "market_bucket"


REQUIRED_ROLES = frozenset(SkillForgeRole)


class SkillForgeConfigurationError(ValueError):
    """Raised with parameter names and sanitized reasons, never resolved values."""

    def __init__(self, issues: Sequence[str]):
        sanitized_issues = tuple(str(issue) for issue in issues)
        self.issues = sanitized_issues
        super().__init__("SkillForge configuration invalid: " + "; ".join(sanitized_issues))


@dataclass(frozen=True)
class SkillForgeParameter:
    """A name-only mapping from one exact SSM path to one logical role."""

    role: SkillForgeRole
    path: str


@dataclass(frozen=True)
class SkillForgeParameterManifest:
    """Validated name-only SkillForge parameter manifest."""

    parameters: tuple[SkillForgeParameter, ...]
    schema_version: int = MANIFEST_SCHEMA_VERSION

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "SkillForgeParameterManifest":
        """Parse and validate a manifest mapping without accepting value fields."""
        if set(raw) != {"schema_version", "parameters"}:
            raise SkillForgeConfigurationError(
                ("manifest: only schema_version and parameters are allowed",)
            )
        if raw.get("schema_version") != MANIFEST_SCHEMA_VERSION:
            raise SkillForgeConfigurationError(("manifest: unsupported schema_version",))

        raw_parameters = raw.get("parameters")
        if not isinstance(raw_parameters, list):
            raise SkillForgeConfigurationError(("manifest: parameters must be a list",))

        parameters: list[SkillForgeParameter] = []
        issues: list[str] = []
        for index, item in enumerate(raw_parameters):
            label = f"parameters[{index}]"
            if not isinstance(item, Mapping):
                issues.append(f"{label}: entry must be an object")
                continue
            if set(item) != {"role", "path"}:
                issues.append(f"{label}: only role and path are allowed")
                continue

            raw_role = item.get("role")
            try:
                role = SkillForgeRole(raw_role)
            except (TypeError, ValueError):
                issues.append(f"{label}: unknown logical role")
                continue

            path = item.get("path")
            if not isinstance(path, str) or not path:
                issues.append(f"{role.value}: parameter path is absent or empty")
                continue
            if path != path.strip() or not _valid_parameter_path(path):
                issues.append(f"{path.strip() or role.value}: malformed parameter path")
                continue
            parameters.append(SkillForgeParameter(role=role, path=path))

        role_counts = {role: 0 for role in REQUIRED_ROLES}
        path_counts: dict[str, int] = {}
        for parameter in parameters:
            role_counts[parameter.role] += 1
            path_counts[parameter.path] = path_counts.get(parameter.path, 0) + 1

        for role in sorted(REQUIRED_ROLES, key=lambda value: value.value):
            count = role_counts[role]
            if count == 0:
                issues.append(f"{role.value}: required logical role is absent")
            elif count > 1:
                issues.append(f"{role.value}: logical role is duplicated")
        for path, count in sorted(path_counts.items()):
            if count > 1:
                issues.append(f"{path}: parameter path is duplicated")
        if len(raw_parameters) != len(REQUIRED_ROLES):
            issues.append("manifest: exactly seven parameter entries are required")

        if issues:
            raise SkillForgeConfigurationError(issues)
        return cls(parameters=tuple(parameters))

    @classmethod
    def from_json_file(cls, path: str | Path) -> "SkillForgeParameterManifest":
        """Load a UTF-8 JSON manifest; no resolved values are read from disk."""
        manifest_path = Path(path)
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SkillForgeConfigurationError(
                (f"{manifest_path}: manifest could not be loaded ({type(exc).__name__})",)
            ) from None
        if not isinstance(raw, Mapping):
            raise SkillForgeConfigurationError((f"{manifest_path}: manifest root must be an object",))
        return cls.from_mapping(raw)


@dataclass(frozen=True)
class SkillForgeConfig:
    """Immutable runtime identifiers resolved from the verified manifest."""

    code_interpreter_id: str
    gateway_id_or_url: str
    knowledge_base_id: str
    memory_id: str
    profile_table_name: str
    progression_table_name: str
    market_bucket_name: str
    region: str = SKILLFORGE_REGION


class SSMClient(Protocol):
    """Narrow protocol used by the resolver and its tests."""

    def get_parameters(self, *, Names: list[str], WithDecryption: bool) -> Mapping[str, Any]:
        """Resolve parameters by exact name."""


def resolve_skillforge_config(
    manifest: SkillForgeParameterManifest,
    *,
    ssm_client: SSMClient | None = None,
) -> SkillForgeConfig:
    """Resolve all seven values from SSM in us-west-2 or fail with no partial result."""
    client = ssm_client or _create_ssm_client()
    paths = [parameter.path for parameter in manifest.parameters]
    try:
        response = client.get_parameters(Names=paths, WithDecryption=True)
    except Exception:
        raise SkillForgeConfigurationError(
            tuple(f"{path}: SSM resolution failed" for path in paths)
        ) from None

    invalid = response.get("InvalidParameters", ())
    parameters = response.get("Parameters", ())
    if not isinstance(invalid, Sequence) or isinstance(invalid, (str, bytes)):
        invalid = ()
    if not isinstance(parameters, Sequence) or isinstance(parameters, (str, bytes)):
        parameters = ()

    issues: list[str] = []
    expected_paths = set(paths)
    for path in invalid:
        if isinstance(path, str) and path in expected_paths:
            issues.append(f"{path}: parameter is absent")

    resolved: dict[str, Mapping[str, Any]] = {}
    for item in parameters:
        if not isinstance(item, Mapping):
            issues.append("SSM response: malformed parameter entry")
            continue
        name = item.get("Name")
        if not isinstance(name, str) or name not in expected_paths:
            issues.append("SSM response: contained an unexpected parameter name")
            continue
        if name in resolved:
            issues.append(f"{name}: resolved parameter is duplicated")
            continue
        resolved[name] = item

    for path in paths:
        if path not in resolved and not any(issue.startswith(f"{path}: parameter is absent") for issue in issues):
            issues.append(f"{path}: parameter is absent")

    role_values: dict[SkillForgeRole, str] = {}
    for parameter in manifest.parameters:
        item = resolved.get(parameter.path)
        if item is None:
            continue
        parameter_type = item.get("Type")
        if parameter_type not in ("String", "SecureString"):
            issues.append(f"{parameter.path}: parameter type must be String or SecureString")
            continue
        data_type = item.get("DataType", "text")
        if data_type != "text":
            issues.append(f"{parameter.path}: parameter data type must be text")
            continue
        value = item.get("Value")
        if not isinstance(value, str) or not value.strip():
            issues.append(f"{parameter.path}: resolved value is empty")
            continue
        value = value.strip()
        if not _valid_role_value(parameter.role, value):
            issues.append(f"{parameter.path}: resolved value does not match {parameter.role.value}")
            continue
        role_values[parameter.role] = value

    if len(set(role_values.values())) != len(role_values):
        issues.append("manifest: multiple logical roles resolved to the same resource identifier")
    if issues:
        raise SkillForgeConfigurationError(issues)

    return SkillForgeConfig(
        code_interpreter_id=role_values[SkillForgeRole.CODE_INTERPRETER],
        gateway_id_or_url=role_values[SkillForgeRole.GATEWAY],
        knowledge_base_id=role_values[SkillForgeRole.KNOWLEDGE_BASE],
        memory_id=role_values[SkillForgeRole.MEMORY],
        profile_table_name=role_values[SkillForgeRole.PROFILE_TABLE],
        progression_table_name=role_values[SkillForgeRole.PROGRESSION_TABLE],
        market_bucket_name=role_values[SkillForgeRole.MARKET_BUCKET],
    )


def resolve_skillforge_config_file(
    manifest_path: str | Path,
    *,
    ssm_client: SSMClient | None = None,
) -> SkillForgeConfig:
    """Load a name-only manifest and resolve its values at runtime."""
    return resolve_skillforge_config(
        SkillForgeParameterManifest.from_json_file(manifest_path),
        ssm_client=ssm_client,
    )


def _create_ssm_client() -> SSMClient:
    """Create an SSM client pinned to the mandatory SkillForge region."""
    import boto3

    return boto3.client("ssm", region_name=SKILLFORGE_REGION)


def _valid_parameter_path(path: str) -> bool:
    return (
        len(path) <= 1011
        and "//" not in path
        and path[-1] != "/"
        and _PARAMETER_PATH.fullmatch(path) is not None
    )


def _valid_role_value(role: SkillForgeRole, value: str) -> bool:
    if role is SkillForgeRole.CODE_INTERPRETER:
        return _CODE_INTERPRETER_ID.fullmatch(value) is not None
    if role is SkillForgeRole.GATEWAY:
        return _GATEWAY_ID.fullmatch(value) is not None or _valid_https_url(value)
    if role is SkillForgeRole.KNOWLEDGE_BASE:
        return _KNOWLEDGE_BASE_ID.fullmatch(value) is not None
    if role is SkillForgeRole.MEMORY:
        return _MEMORY_ID.fullmatch(value) is not None
    if role in (SkillForgeRole.PROFILE_TABLE, SkillForgeRole.PROGRESSION_TABLE):
        return _DYNAMODB_TABLE_NAME.fullmatch(value) is not None
    if role is SkillForgeRole.MARKET_BUCKET:
        return _S3_BUCKET_NAME.fullmatch(value) is not None
    return False


def _valid_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and parsed.fragment == ""
    )


__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "REQUIRED_ROLES",
    "SKILLFORGE_REGION",
    "SkillForgeConfig",
    "SkillForgeConfigurationError",
    "SkillForgeParameter",
    "SkillForgeParameterManifest",
    "SkillForgeRole",
    "resolve_skillforge_config",
    "resolve_skillforge_config_file",
]
