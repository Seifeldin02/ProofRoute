"""Focused unit tests for the name-only SkillForge configuration resolver."""

from dataclasses import FrozenInstanceError

import pytest

from agent import skillforge_config as subject
from agent.skillforge_config import (
    SKILLFORGE_REGION,
    SkillForgeConfigurationError,
    SkillForgeParameterManifest,
    resolve_skillforge_config,
)


ROLES = (
    "code_interpreter",
    "gateway",
    "knowledge_base",
    "memory",
    "profile_table",
    "progression_table",
    "market_bucket",
)
VALUES = {
    "code_interpreter": "SkillForgeCI_1-ABCDEFGHIJ",
    "gateway": "skillforge-gateway-abcdefghij",
    "knowledge_base": "A1B2C3D4E5",
    "memory": "SkillForgeMemory-ABCDEFGHIJ",
    "profile_table": "skillforge-profile-table",
    "progression_table": "skillforge-progression-table",
    "market_bucket": "skillforge-market-bucket",
}


def manifest_mapping() -> dict:
    return {
        "schema_version": 1,
        "parameters": [
            {"role": role, "path": f"/app/workshop/proofroute/{role}"}
            for role in ROLES
        ],
    }


def ssm_parameter(role: str, *, value: str | None = None) -> dict:
    return {
        "Name": f"/app/workshop/proofroute/{role}",
        "Type": "String",
        "Value": VALUES[role] if value is None else value,
        "DataType": "text",
    }


class FakeSSMClient:
    def __init__(self, response: dict):
        self.response = response
        self.calls: list[dict] = []

    def get_parameters(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def test_resolves_exactly_seven_typed_values_at_runtime():
    manifest = SkillForgeParameterManifest.from_mapping(manifest_mapping())
    client = FakeSSMClient({"Parameters": [ssm_parameter(role) for role in reversed(ROLES)]})

    config = resolve_skillforge_config(manifest, ssm_client=client)

    assert config.code_interpreter_id == VALUES["code_interpreter"]
    assert config.gateway_id_or_url == VALUES["gateway"]
    assert config.knowledge_base_id == VALUES["knowledge_base"]
    assert config.memory_id == VALUES["memory"]
    assert config.profile_table_name == VALUES["profile_table"]
    assert config.progression_table_name == VALUES["progression_table"]
    assert config.market_bucket_name == VALUES["market_bucket"]
    assert config.region == "us-west-2"
    assert client.calls == [
        {
            "Names": [f"/app/workshop/proofroute/{role}" for role in ROLES],
            "WithDecryption": True,
        }
    ]
    with pytest.raises(FrozenInstanceError):
        config.region = "us-east-1"


def test_manifest_rejects_resolved_values_and_other_non_name_fields():
    raw = manifest_mapping()
    raw["parameters"][0]["value"] = "must-not-be-committed"

    with pytest.raises(SkillForgeConfigurationError) as error:
        SkillForgeParameterManifest.from_mapping(raw)

    assert "must-not-be-committed" not in str(error.value)
    assert "only role and path are allowed" in str(error.value)


@pytest.mark.parametrize(
    ("mutate", "expected_reason"),
    [
        (
            lambda raw: raw["parameters"].pop(),
            "required logical role is absent",
        ),
        (
            lambda raw: raw["parameters"].__setitem__(
                1,
                {
                    "role": raw["parameters"][0]["role"],
                    "path": "/app/workshop/proofroute/duplicate-role",
                },
            ),
            "logical role is duplicated",
        ),
        (
            lambda raw: raw["parameters"].__setitem__(
                1,
                {
                    "role": raw["parameters"][1]["role"],
                    "path": raw["parameters"][0]["path"],
                },
            ),
            "parameter path is duplicated",
        ),
        (
            lambda raw: raw["parameters"][0].__setitem__("path", ""),
            "parameter path is absent or empty",
        ),
        (
            lambda raw: raw["parameters"][0].__setitem__(
                "path", "/not-authoritative/code-interpreter"
            ),
            "malformed parameter path",
        ),
    ],
)
def test_manifest_fails_closed_for_incomplete_duplicate_or_malformed_entries(
    mutate, expected_reason
):
    raw = manifest_mapping()
    mutate(raw)

    with pytest.raises(SkillForgeConfigurationError) as error:
        SkillForgeParameterManifest.from_mapping(raw)

    assert expected_reason in str(error.value)


@pytest.mark.parametrize(
    ("response", "expected_reason"),
    [
        (
            {
                "Parameters": [ssm_parameter(role) for role in ROLES[:-1]],
                "InvalidParameters": [f"/app/workshop/proofroute/{ROLES[-1]}"],
            },
            "parameter is absent",
        ),
        (
            {
                "Parameters": [ssm_parameter(role) for role in ROLES]
                + [ssm_parameter(ROLES[0])]
            },
            "resolved parameter is duplicated",
        ),
        (
            {
                "Parameters": [
                    ssm_parameter(role, value="" if role == ROLES[0] else None)
                    for role in ROLES
                ]
            },
            "resolved value is empty",
        ),
        (
            {
                "Parameters": [
                    ssm_parameter(
                        role,
                        value=VALUES["market_bucket"] if role == "knowledge_base" else None,
                    )
                    for role in ROLES
                ]
            },
            "resolved value does not match knowledge_base",
        ),
    ],
)
def test_resolver_fails_closed_without_returning_partial_configuration(
    response, expected_reason
):
    manifest = SkillForgeParameterManifest.from_mapping(manifest_mapping())

    with pytest.raises(SkillForgeConfigurationError) as error:
        resolve_skillforge_config(manifest, ssm_client=FakeSSMClient(response))

    assert expected_reason in str(error.value)
    assert VALUES["code_interpreter"] not in str(error.value)
    assert VALUES["market_bucket"] not in str(error.value)


def test_ssm_client_is_always_created_in_skillforge_region(monkeypatch):
    calls = []
    sentinel = object()

    def fake_client(service_name, **kwargs):
        calls.append((service_name, kwargs))
        return sentinel

    monkeypatch.setattr("boto3.client", fake_client)

    assert subject._create_ssm_client() is sentinel
    assert calls == [("ssm", {"region_name": SKILLFORGE_REGION})]
