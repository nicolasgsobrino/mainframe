"""Resolución del laboratorio por identificador lógico (nunca por Instance ID).

Ningún test llama a AWS: el resolutor AWS se ejercita con un cliente EC2/SSM
falso que devuelve respuestas de `DescribeInstances` ya formadas.
"""
from __future__ import annotations

import pytest

from app.labs import (
    ERROR_AMBIGUOUS,
    ERROR_NOT_FOUND,
    ERROR_TAGS,
    AwsLabResolver,
    LabResolutionError,
    check_lab_tags,
    default_lab_target,
    get_lab_resolver,
    required_lab_tags,
)

LAB_ID = "linux-patching-01"
INSTANCE = "i-0123456789abcdef0"


def instance(instance_id=INSTANCE, tags=None, state="running"):
    tags = {"msr-poc": "true", "msr-lab-id": LAB_ID,
            "msr-environment": "sandbox"} if tags is None else tags
    return {
        "InstanceId": instance_id,
        "State": {"Name": state},
        "ImageId": "ami-0b2ab3a97a77bd35e",
        "PrivateIpAddress": "10.0.0.10",
        "Placement": {"AvailabilityZone": "eu-north-1a"},
        "Tags": [{"Key": k, "Value": v} for k, v in tags.items()],
    }


class FakeEc2:
    def __init__(self, instances):
        self._instances = instances
        self.calls: list[dict] = []

    def describe_instances(self, **kwargs):
        self.calls.append(kwargs)
        return {"Reservations": [{"OwnerId": "133789123239",
                                  "Instances": list(self._instances)}]}


class FakeSsm:
    def describe_instance_information(self, **_kwargs):
        return {"InstanceInformationList": [{"PingStatus": "Online"}]}


class FakeProvider:
    name = "aws-automation"

    def __init__(self, instances):
        self.ec2 = FakeEc2(instances)
        self.ssm = FakeSsm()


def resolver(aws_settings, instances) -> AwsLabResolver:
    aws_settings.lab_logical_id = LAB_ID
    return AwsLabResolver(aws_settings, FakeProvider(instances))


def test_exactly_one_tagged_instance_resolves_the_current_instance_id(aws_settings):
    lab_resolver = resolver(aws_settings, [instance()])

    resolved = lab_resolver.resolve(LAB_ID)

    assert resolved.instance_id == INSTANCE
    assert resolved.state == "running"
    assert resolved.region == "eu-north-1"
    assert resolved.ssm_managed is True
    # El filtro se construye con los tags obligatorios, nunca con un ID libre.
    names = {f["Name"] for f in lab_resolver._provider.ec2.calls[0]["Filters"]}
    assert names == {"instance-state-name", "tag:msr-poc", "tag:msr-lab-id"}


def test_zero_instances_is_reported_as_lab_target_not_found(aws_settings):
    with pytest.raises(LabResolutionError) as excinfo:
        resolver(aws_settings, []).resolve(LAB_ID)

    assert excinfo.value.code == ERROR_NOT_FOUND


def test_more_than_one_instance_is_ambiguous_and_never_picks_one(aws_settings):
    second = instance(instance_id="i-0fedcba9876543210")

    with pytest.raises(LabResolutionError) as excinfo:
        resolver(aws_settings, [instance(), second]).resolve(LAB_ID)

    assert excinfo.value.code == ERROR_AMBIGUOUS
    assert set(excinfo.value.candidates) == {INSTANCE, second["InstanceId"]}


def test_missing_required_tags_are_rejected(aws_settings):
    untagged = instance(tags={"msr-poc": "true"})

    with pytest.raises(LabResolutionError) as excinfo:
        resolver(aws_settings, [untagged]).resolve(LAB_ID)

    assert excinfo.value.code == ERROR_TAGS


def test_terminated_instances_are_never_active_targets(aws_settings):
    lab_resolver = resolver(aws_settings, [instance()])

    lab_resolver.resolve(LAB_ID)

    states = lab_resolver._provider.ec2.calls[0]["Filters"][0]["Values"]
    assert "terminated" not in states
    assert "shutting-down" not in states


def test_required_tags_and_missing_tags_helpers(settings):
    settings.lab_tag_key = "msr-lab-id"
    expected = required_lab_tags(settings, LAB_ID)

    assert expected["msr-lab-id"] == LAB_ID
    assert check_lab_tags(expected, settings, LAB_ID) == []
    assert check_lab_tags({}, settings, LAB_ID)


def test_mock_resolver_does_not_touch_aws(settings, repo):
    settings.lab_logical_id = LAB_ID
    repo.upsert_lab_target(default_lab_target(settings, LAB_ID))
    mock_resolver = get_lab_resolver(settings, type("P", (), {"name": "mock"})(), repo)

    with pytest.raises(LabResolutionError):
        mock_resolver.resolve(LAB_ID)  # aún no hay instancia registrada

    lab = repo.get_lab_target(LAB_ID)
    lab.current_instance_id = INSTANCE
    repo.upsert_lab_target(lab)

    assert mock_resolver.resolve(LAB_ID).instance_id == INSTANCE
    assert mock_resolver.source == "mock"


def test_default_lab_target_has_no_fixed_instance_id(settings):
    lab = default_lab_target(settings, LAB_ID)

    assert lab.current_instance_id is None
    assert lab.required_tags == required_lab_tags(settings, LAB_ID)
