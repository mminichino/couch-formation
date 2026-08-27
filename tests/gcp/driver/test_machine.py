from __future__ import annotations

import pytest

from couchformation.gcp.driver.base import CloudBase
from couchformation.gcp.driver.machine import MachineType

pytestmark = [pytest.mark.driver, pytest.mark.cf_gcp]



def test_list_returns_machine_types(gcp_parameters):
    base = CloudBase(gcp_parameters)
    machine = MachineType(gcp_parameters)
    zone = base.zones()[0]
    result = machine.list(zone)
    assert len(result) > 0
    assert result[0]["cpu"] > 0
    assert result[0]["memory"] > 0


def test_get_machine_returns_match(gcp_parameters):
    base = CloudBase(gcp_parameters)
    machine = MachineType(gcp_parameters)
    zone = base.zones()[0]
    result = machine.get_machine("4x16", zone)
    assert result is not None
    assert result["cpu"] == 4
    assert result["memory"] == 16384


def test_details_returns_block(gcp_parameters):
    base = CloudBase(gcp_parameters)
    machine = MachineType(gcp_parameters)
    zone = base.zones()[0]
    types = machine.list(zone)
    result = machine.details(types[0]["name"])
    assert result["name"] == types[0]["name"]
