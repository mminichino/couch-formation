"""Tests for ``couchformation.aws.driver.machine``."""

from __future__ import annotations

import pytest

from couchformation.aws.driver.base import AWSDriverError, EmptyResultSet
from couchformation.aws.driver.machine import MachineType


@pytest.fixture
def machine(aws_clients):
    return MachineType({})


def _instance_type(
    name="m5.xlarge",
    cpu=4,
    memory=16384,
    archs=("x86_64",),
    clock=3.0,
    network="Up to 10 Gigabit",
    nvme="supported",
    hypervisor="nitro",
):
    return {
        "InstanceType": name,
        "VCpuInfo": {"DefaultVCpus": cpu},
        "MemoryInfo": {"SizeInMiB": memory},
        "ProcessorInfo": {
            "SupportedArchitectures": list(archs),
            "SustainedClockSpeedInGhz": clock,
        },
        "NetworkInfo": {"NetworkPerformance": network},
        "EbsInfo": {"NvmeSupport": nvme},
        "Hypervisor": hypervisor,
    }


def test_list_returns_blocks_and_paginates(machine, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_instance_types.side_effect = [
        {
            "InstanceTypes": [_instance_type("m5.large", cpu=2, memory=8192)],
            "NextToken": "n",
        },
        {"InstanceTypes": [_instance_type("m5.xlarge", cpu=4, memory=16384)]},
    ]
    result = machine.list()
    assert [m["name"] for m in result] == ["m5.large", "m5.xlarge"]
    assert result[0] == {
        "name": "m5.large",
        "cpu": 2,
        "memory": 8192,
        "arch": ["x86_64"],
        "clock": 3.0,
        "network": "Up to 10 Gigabit",
        "nvme": "supported",
        "hypervisor": "nitro",
    }


def test_list_filters_passed(machine, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_instance_types.return_value = {
        "InstanceTypes": [_instance_type()]
    }
    machine.list(architecture="arm64")
    _, kwargs = ec2.describe_instance_types.call_args
    filters = kwargs["Filters"]
    arch_filter = next(
        f for f in filters
        if f["Name"] == "processor-info.supported-architecture"
    )
    assert arch_filter["Values"] == ["arm64"]


def test_list_empty_raises(machine, aws_clients):
    aws_clients.get("ec2").describe_instance_types.return_value = {
        "InstanceTypes": []
    }
    with pytest.raises(EmptyResultSet):
        machine.list()


def test_list_error_raises(machine, aws_clients):
    aws_clients.get("ec2").describe_instance_types.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error getting instance types"):
        machine.list()


def test_get_machine_zones_returns_locations(machine, aws_clients):
    aws_clients.get("ec2").describe_instance_type_offerings.return_value = {
        "InstanceTypeOfferings": [
            {"Location": "us-east-1a"},
            {"Location": "us-east-1b"},
        ]
    }
    assert machine.get_machine_zones("m5.large") == [
        "us-east-1a",
        "us-east-1b",
    ]


def test_get_machine_zones_error_raises(machine, aws_clients):
    aws_clients.get("ec2").describe_instance_type_offerings.side_effect = (
        RuntimeError("x")
    )
    with pytest.raises(AWSDriverError):
        machine.get_machine_zones("m5.large")


def test_get_machine_types_filters_by_cpu_memory(machine, aws_clients):
    aws_clients.get("ec2").describe_instance_types.return_value = {
        "InstanceTypes": [
            _instance_type("m5.large", cpu=2, memory=8192),
            _instance_type("m5.xlarge", cpu=4, memory=16384),
        ]
    }
    result = machine.get_machine_types()
    machine_types = {m["machine_type"] for m in result}
    assert "2x8" in machine_types
    assert "4x16" in machine_types


def test_get_machine_returns_matching(machine, aws_clients):
    aws_clients.get("ec2").describe_instance_types.return_value = {
        "InstanceTypes": [_instance_type("m5.large", cpu=2, memory=8192)]
    }
    result = machine.get_machine("2x8")
    assert result is not None
    assert result["name"] == "m5.large"
    assert result["machine_type"] == "2x8"


def test_get_machine_no_match_returns_none(machine, aws_clients):
    aws_clients.get("ec2").describe_instance_types.return_value = {
        "InstanceTypes": [_instance_type("m5.large", cpu=2, memory=8192)]
    }
    assert machine.get_machine("does-not-exist") is None


def test_get_next_machine_returns_following_in_list(machine, aws_clients):
    aws_clients.get("ec2").describe_instance_types.return_value = {
        "InstanceTypes": [
            _instance_type("m5.large", cpu=2, memory=8192),
            _instance_type("m5.xlarge", cpu=4, memory=16384),
        ]
    }
    next_machine = machine.get_next_machine("m5.large")
    assert next_machine["name"] == "m5.xlarge"


def test_details_returns_block(machine, aws_clients):
    aws_clients.get("ec2").describe_instance_types.return_value = {
        "InstanceTypes": [_instance_type()]
    }
    result = machine.details("m5.xlarge")
    assert result["name"] == "m5.xlarge"
    assert result["cpu"] == 4
    assert result["memory"] == 16384


def test_details_empty_raises(machine, aws_clients):
    aws_clients.get("ec2").describe_instance_types.return_value = {
        "InstanceTypes": []
    }
    with pytest.raises(EmptyResultSet, match="can not find instance type"):
        machine.details("m5.xlarge")


def test_details_error_raises(machine, aws_clients):
    aws_clients.get("ec2").describe_instance_types.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError):
        machine.details("m5.xlarge")
