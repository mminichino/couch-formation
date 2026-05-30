from __future__ import annotations

import pytest

from couchformation.azure.driver.disk import Disk
from couchformation.azure.driver.resource_group import ResourceGroup
from tests.azure.driver.conftest import unique_name

pytestmark = pytest.mark.cf_azure


def test_disk_create_details_delete(azure_parameters, azure_rg, cleanup):
    base = ResourceGroup(azure_parameters)
    disk = Disk(azure_parameters)
    zone = base.zones()[0]
    disk_name = unique_name(f"{azure_parameters['project']}-disk")

    disk.create(azure_rg, azure_parameters["region"], zone, 32, disk_name)
    cleanup(lambda: disk.delete(disk_name, azure_rg))

    details = disk.details(disk_name, azure_rg)
    assert details is not None
    assert details["name"] == disk_name

    disk.delete(disk_name, azure_rg)
    assert disk.details(disk_name, azure_rg) is None
