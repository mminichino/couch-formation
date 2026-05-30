from __future__ import annotations

import pytest

from couchformation.gcp.driver.base import CloudBase
from couchformation.gcp.driver.disk import Disk
from tests.gcp.driver.conftest import unique_name

pytestmark = pytest.mark.cf_gcp


def test_disk_create_list_delete(gcp_parameters, cleanup):
    base = CloudBase(gcp_parameters)
    disk = Disk(gcp_parameters)
    zone = base.zones()[0]
    disk_name = unique_name(f"{gcp_parameters['project']}-disk")

    disk.create(disk_name, zone, "10")
    cleanup(lambda: disk.delete(disk_name, zone))

    found = disk.find(disk_name)
    assert found is not None
    assert found["name"] == disk_name

    disk_list = disk.list(zone)
    assert any(item["name"] == disk_name for item in disk_list)

    disk.delete(disk_name, zone)
    assert disk.find(disk_name) is None
