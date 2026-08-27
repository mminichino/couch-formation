from __future__ import annotations

import pytest

from couchformation.gcp.driver.network import Network
from couchformation.gcp.driver.subnet import Subnet
from tests.gcp.driver.conftest import unique_name

pytestmark = [pytest.mark.driver, pytest.mark.cf_gcp]



def test_network_create_list_details_delete(gcp_parameters, cidr_util, cleanup):
    network = Network(gcp_parameters)
    vpc_name = unique_name(f"{gcp_parameters['project']}-vpc")

    network.create(vpc_name)
    cleanup(lambda: network.delete(vpc_name))

    network_list = network.list()
    assert any(item["name"] == vpc_name for item in network_list)

    details = network.details(vpc_name)
    assert details is not None
    assert details["name"] == vpc_name

    network.delete(vpc_name)
    assert network.details(vpc_name) is None


def test_subnet_create_details_delete(gcp_parameters, cidr_util, cleanup):
    network = Network(gcp_parameters)
    subnet_drv = Subnet(gcp_parameters)

    vpc_name = unique_name(f"{gcp_parameters['project']}-vpc")
    subnet_name = unique_name(f"{gcp_parameters['project']}-subnet")
    subnet_cidr = next(cidr_util.get_next_subnet())

    network.create(vpc_name)
    cleanup(lambda: network.delete(vpc_name))

    subnet_drv.create(subnet_name, vpc_name, subnet_cidr)
    cleanup(lambda: subnet_drv.delete(subnet_name))

    subnets = subnet_drv.list(vpc_name)
    assert any(item["name"] == subnet_name for item in subnets)

    details = subnet_drv.details(subnet_name)
    assert details is not None
    assert details["cidr"] == subnet_cidr
    assert details["network"] == vpc_name

    subnet_drv.delete(subnet_name)
    assert subnet_drv.details(subnet_name) is None
