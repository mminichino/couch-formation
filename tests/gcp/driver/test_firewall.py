from __future__ import annotations

import pytest

from couchformation.gcp.driver.firewall import Firewall
from couchformation.gcp.driver.network import Network
from tests.gcp.driver.conftest import unique_name

pytestmark = pytest.mark.cf_gcp


def test_firewall_create_details_delete(gcp_parameters, cidr_util, cleanup):
    network = Network(gcp_parameters)
    firewall = Firewall(gcp_parameters)

    vpc_name = unique_name(f"{gcp_parameters['project']}-vpc")
    fw_name = unique_name(f"{gcp_parameters['project']}-fw")
    vpc_cidr = cidr_util.get_next_network()

    network.create(vpc_name)
    cleanup(lambda: network.delete(vpc_name))

    firewall.create_ingress(fw_name, vpc_name, vpc_cidr, "tcp", ["22"])
    cleanup(lambda: firewall.delete(fw_name))

    details = firewall.details(fw_name)
    assert details is not None
    assert details["name"] == fw_name

    firewall_list = firewall.list()
    assert any(item["name"] == fw_name for item in firewall_list)

    firewall.delete(fw_name)
    assert firewall.details(fw_name) is None
