from __future__ import annotations

import pytest
import logging

from couchformation.aws.driver.dns import DNS
from couchformation.aws.driver.network import Network
from tests.aws.driver.conftest import unique_name, domain_name

logger = logging.getLogger('tests.aws.driver.test_dns')
pytestmark = [pytest.mark.driver, pytest.mark.cf_aws]



def test_public_hosted_zone_lifecycle(aws_parameters, cleanup):
    dns = DNS(aws_parameters)
    domain = domain_name()

    zone_id = dns.create(domain, region=aws_parameters["region"])
    logger.debug(f"Created zone {zone_id}")
    cleanup(lambda: dns.delete(zone_id))
    assert zone_id

    details = dns.details(zone_id)
    assert details is not None
    assert details["Name"].startswith(domain)

    assert dns.zone_id(domain) == zone_id

    record_status = dns.add_record(zone_id, f"host.{domain}", ["1.2.3.4"])
    assert record_status

    records = dns.record_sets(zone_id, "A")
    assert "1.2.3.4" in records

    dns.delete_record(zone_id, f"host.{domain}", ["1.2.3.4"])
    dns.delete(zone_id)
    assert dns.details(zone_id) is None


def test_private_hosted_zone_associate_disassociate(aws_parameters, cidr_util, cleanup):
    network = Network(aws_parameters)
    dns = DNS(aws_parameters)

    vpc_name = unique_name(f"{aws_parameters['project']}-vpc")
    domain = domain_name()
    vpc_cidr = cidr_util.get_next_network()

    vpc_id = network.create(vpc_name, vpc_cidr)
    cleanup(lambda: network.delete(vpc_id))

    zone_id = dns.create(domain, vpc_id=vpc_id, region=aws_parameters["region"])
    logger.debug(f"Created zone {zone_id}")
    cleanup(lambda: dns.delete(zone_id))

    associations = dns.list_associations(vpc_id, aws_parameters["region"])
    logger.debug(f"Associations: {associations}")
    assert any(item["HostedZoneId"] == zone_id for item in associations)
    assert dns.associate(zone_id, vpc_id, aws_parameters["region"]) in (None, "PENDING", "INSYNC")

    dns.delete(zone_id)
