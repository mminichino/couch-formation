from __future__ import annotations

import pytest

from couchformation.azure.driver.network import Network, SecurityGroup, Subnet
from tests.azure.driver.conftest import unique_name

pytestmark = [pytest.mark.driver, pytest.mark.cf_azure]



def test_network_create_list_delete(azure_parameters, azure_rg, cidr_util, cleanup):
    network = Network(azure_parameters)
    vpc_name = unique_name(f"{azure_parameters['project']}-vpc")
    vpc_cidr = cidr_util.get_next_network()

    network.create(vpc_name, vpc_cidr, azure_rg)
    cleanup(lambda: network.delete(vpc_name, azure_rg))

    network_list = network.list(azure_rg)
    assert any(item["name"] == vpc_name for item in network_list)

    details = network.details(vpc_name, azure_rg)
    assert details is not None
    assert details.name == vpc_name

    network.delete(vpc_name, azure_rg)
    assert network.details(vpc_name, azure_rg) is None


def test_subnet_and_nsg_create_delete(azure_parameters, azure_rg, cidr_util, cleanup):
    network = Network(azure_parameters)
    subnet_drv = Subnet(azure_parameters)
    nsg = SecurityGroup(azure_parameters)

    vpc_name = unique_name(f"{azure_parameters['project']}-vpc")
    subnet_name = unique_name(f"{azure_parameters['project']}-subnet")
    nsg_name = unique_name(f"{azure_parameters['project']}-nsg")
    vpc_cidr = cidr_util.get_next_network()
    subnet_cidr = next(cidr_util.get_next_subnet())

    network.create(vpc_name, vpc_cidr, azure_rg)
    cleanup(lambda: network.delete(vpc_name, azure_rg))

    nsg_resource = nsg.create(nsg_name, azure_rg)
    cleanup(lambda: nsg.delete(nsg_name, azure_rg))
    nsg.add_rule("AllowSSH", nsg_name, ["22"], 100, azure_rg)

    subnet_resource = subnet_drv.create(subnet_name, vpc_name, subnet_cidr, nsg_resource.id, azure_rg)
    cleanup(lambda: subnet_drv.delete(vpc_name, subnet_name, azure_rg))
    assert subnet_resource.id

    subnet_details = subnet_drv.details(vpc_name, subnet_name, azure_rg)
    assert subnet_details is not None
    assert subnet_details["cidr"] == subnet_cidr

    nsg_details = nsg.details(nsg_name, azure_rg)
    assert nsg_details is not None
    assert len(nsg_details["rules"]) > 0

    subnet_drv.delete(vpc_name, subnet_name, azure_rg)
    nsg.delete(nsg_name, azure_rg)
