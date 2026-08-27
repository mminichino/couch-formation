from __future__ import annotations

import pytest

from couchformation.aws.driver.network import Network, Subnet
from tests.aws.driver.conftest import unique_name

pytestmark = [pytest.mark.driver, pytest.mark.cf_aws]



def test_network_create_list_details_delete(aws_parameters, cidr_util, cleanup):
    network = Network(aws_parameters)
    name = unique_name(f"{aws_parameters['project']}-vpc")
    vpc_cidr = cidr_util.get_next_network()

    vpc_id = network.create(name, vpc_cidr, tags={"Environment": "pytest"})
    cleanup(lambda: network.delete(vpc_id))

    network.enable_dns_hostnames(vpc_id)

    listed = network.list(name=name)
    assert listed is not None
    assert any(item["id"] == vpc_id for item in listed)

    details = network.details(vpc_id)
    assert details is not None
    assert details["id"] == vpc_id
    assert details["cidr"] == vpc_cidr

    assert vpc_cidr in list(network.cidr_list)

    network.delete(vpc_id)
    assert network.details(vpc_id) is None


def test_subnet_create_details_delete(aws_parameters, cidr_util, cleanup):
    network = Network(aws_parameters)
    subnet_drv = Subnet(aws_parameters)
    base = network
    zones = base.zones()

    vpc_name = unique_name(f"{aws_parameters['project']}-vpc")
    subnet_name = unique_name(f"{aws_parameters['project']}-subnet")
    vpc_cidr = cidr_util.get_next_network()
    subnet_cidr = next(cidr_util.get_next_subnet())

    vpc_id = network.create(vpc_name, vpc_cidr)
    cleanup(lambda: network.delete(vpc_id))

    subnet_id = subnet_drv.create(
        subnet_name, vpc_id, zones[0], subnet_cidr, tags={"Environment": "pytest"}
    )
    cleanup(lambda: subnet_drv.delete(subnet_id))

    subnets = subnet_drv.list(vpc_id)
    assert any(item["name"] == subnet_id for item in subnets)

    details = subnet_drv.details(subnet_id)
    assert details is not None
    assert details["cidr"] == subnet_cidr
    assert details["vpc"] == vpc_id
    assert details["zone"] == zones[0]

    subnet_drv.delete(subnet_id)
    assert subnet_drv.details(subnet_id) is None
