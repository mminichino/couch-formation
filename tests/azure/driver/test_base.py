from __future__ import annotations

import pytest

from couchformation.azure.driver.base import AzureDriverError, EmptyResultSet
from couchformation.azure.driver.resource_group import ResourceGroup

pytestmark = [pytest.mark.driver, pytest.mark.cf_azure]



def test_init_sets_region_and_zones(azure_parameters):
    base = ResourceGroup(azure_parameters)
    assert base.region == azure_parameters["region"]
    assert len(base.azure_availability_zones) > 0


def test_test_session_success(azure_parameters):
    ResourceGroup(azure_parameters).test_session()


def test_credentials_returns_azure_model(azure_parameters):
    creds = ResourceGroup(azure_parameters).credentials()
    assert creds.subscription_id
    assert creds.tenant_id


def test_zones_returns_sorted_unique(azure_parameters):
    base = ResourceGroup(azure_parameters)
    zones = base.zones()
    assert zones == sorted(set(zones))
    assert len(zones) > 0


def test_resource_group_create_get_delete(azure_parameters):
    rg = ResourceGroup(azure_parameters)
    rg_name = f"{azure_parameters['project']}-rg-test"
    location = azure_parameters["region"]

    created = rg.create_rg(rg_name, location)
    assert created.get("name") == rg_name or created.get("id")

    found = rg.get_rg(rg_name, location)
    assert found is not None

    listed = rg.list_rg(location=location)
    assert any(item["name"] == rg_name for item in listed)

    rg.delete_rg(rg_name)
    assert rg.get_rg(rg_name, location) is None


def test_error_class_hierarchy():
    assert issubclass(AzureDriverError, Exception)
    assert issubclass(EmptyResultSet, Exception)
