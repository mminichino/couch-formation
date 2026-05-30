from __future__ import annotations

import pytest

from couchformation.gcp.driver.dns import DNS
from tests.gcp.driver.conftest import unique_name, domain_name

pytestmark = pytest.mark.cf_gcp


def test_managed_zone_lifecycle(gcp_parameters, cleanup):
    dns = DNS(gcp_parameters)
    domain = domain_name()
    zone_name = unique_name("cf-zone")

    created_name = dns.create(domain, zone_name=zone_name)
    cleanup(lambda: dns.delete(created_name, recursive=True))
    assert created_name == zone_name

    details = dns.details(zone_name)
    assert details is not None
    assert details["dnsName"].startswith(domain)

    assert dns.zone_name(domain) == zone_name

    dns.add_record(zone_name, f"host.{domain}", ["1.2.3.4"])
    records = dns.record_sets(zone_name, "A")
    assert "1.2.3.4" in records

    dns.delete(zone_name, recursive=True)
    assert dns.details(zone_name) is None
