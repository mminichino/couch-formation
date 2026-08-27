from __future__ import annotations

import pytest

from couchformation.azure.driver.machine import MachineType
from couchformation.azure.driver.resource_group import ResourceGroup

pytestmark = [pytest.mark.driver, pytest.mark.cf_azure]



def test_get_machine_returns_match(azure_parameters):
    machine = MachineType(azure_parameters)
    result = machine.get_machine("4x16", azure_parameters["region"])
    assert result is not None
    assert result["cpu"] == 4
    assert result["memory"] == 16384


def test_list_returns_machine_types(azure_parameters):
    machine = MachineType(azure_parameters)
    result = machine.list(azure_parameters["region"])
    assert len(result) > 0
    assert result[0]["name"]


def test_details_returns_block(azure_parameters):
    machine = MachineType(azure_parameters)
    match = machine.get_machine("2x8", azure_parameters["region"])
    result = machine.details(match["name"])
    assert result["name"] == match["name"]
