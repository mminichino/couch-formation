from __future__ import annotations

import pytest

from couchformation.aws.driver.machine import MachineType

pytestmark = [pytest.mark.driver, pytest.mark.cf_aws]



def test_list_returns_instance_types(aws_parameters):
    machine = MachineType(aws_parameters)
    result = machine.list()
    assert len(result) > 0
    assert result[0]["name"]
    assert result[0]["cpu"] > 0
    assert result[0]["memory"] > 0


def test_get_machine_zones(aws_parameters):
    machine = MachineType(aws_parameters)
    zones = machine.get_machine_zones("t3.micro")
    assert len(zones) > 0


def test_get_machine_types(aws_parameters):
    machine = MachineType(aws_parameters)
    result = machine.get_machine_types()
    assert len(result) > 0
    assert all("machine_type" in item for item in result)


def test_get_machine_returns_match(aws_parameters):
    machine = MachineType(aws_parameters)
    result = machine.get_machine("2x8")
    assert result is not None
    assert result["cpu"] == 2
    assert result["memory"] == 8192


def test_details_returns_block(aws_parameters):
    machine = MachineType(aws_parameters)
    result = machine.details("t3.micro")
    assert result["name"] == "t3.micro"
    assert result["cpu"] > 0
