from __future__ import annotations

import pytest

from couchformation.azure.driver.dns import DNS
from tests.azure.driver.conftest import domain_name

pytestmark = [pytest.mark.driver, pytest.mark.cf_azure]



def test_dns_zone_lifecycle(azure_parameters, azure_rg, cleanup):
    dns = DNS(azure_parameters)
    domain = domain_name()

    created = dns.create(domain, azure_rg)
    cleanup(lambda: dns.delete(domain, azure_rg))
    assert created == domain

    details = dns.details(domain)
    assert details is not None
    assert details["name"] == domain

    assert dns.zone_name(domain) == domain
    assert dns.zone_rg(domain) == azure_rg

    dns.delete(domain, azure_rg)
    assert dns.details(domain) is None
