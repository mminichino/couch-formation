from __future__ import annotations

import pytest

from couchformation.gcp.driver.base import CloudBase, GCPDriverError, EmptyResultSet

pytestmark = [pytest.mark.driver, pytest.mark.cf_gcp]



def test_init_sets_project_and_region(gcp_parameters):
    base = CloudBase(gcp_parameters)
    assert base.region == gcp_parameters["region"]
    assert base.project
    assert len(base.gcp_zone_list) > 0


def test_test_session_success(gcp_parameters):
    CloudBase(gcp_parameters).test_session()


def test_credentials_returns_gcp_model(gcp_parameters):
    creds = CloudBase(gcp_parameters).credentials()
    assert creds.project_id
    assert creds.project_number


def test_zones_returns_sorted_unique(gcp_parameters):
    base = CloudBase(gcp_parameters)
    zones = base.zones()
    assert zones == sorted(set(zones))
    assert all(z.startswith(gcp_parameters["region"]) for z in zones)


def test_error_class_hierarchy():
    assert issubclass(GCPDriverError, Exception)
    assert issubclass(EmptyResultSet, Exception)
