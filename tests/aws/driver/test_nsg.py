from __future__ import annotations

import pytest

from couchformation.aws.driver.network import Network
from couchformation.aws.driver.nsg import SecurityGroup
from tests.aws.driver.conftest import unique_name

pytestmark = [pytest.mark.driver, pytest.mark.cf_aws]



def test_security_group_create_ingress_delete(aws_parameters, cidr_util, cleanup):
    network = Network(aws_parameters)
    sg = SecurityGroup(aws_parameters)

    vpc_name = unique_name(f"{aws_parameters['project']}-vpc")
    sg_name = unique_name(f"{aws_parameters['project']}-sg")
    vpc_cidr = cidr_util.get_next_network()

    vpc_id = network.create(vpc_name, vpc_cidr)
    cleanup(lambda: network.delete(vpc_id))

    sg_id = sg.create(sg_name, "pytest security group", vpc_id, tags={"Environment": "pytest"})
    cleanup(lambda: sg.delete(sg_id))

    assert sg.add_ingress(sg_id, "tcp", 22, 22, "0.0.0.0/0") is True
    assert sg.add_egress(sg_id, "tcp", 0, 65535, "0.0.0.0/0") is True

    details = sg.details(sg_id)
    assert details is not None
    assert details["id"] == sg_id
    assert details["vpc"] == vpc_id

    listed = sg.list(vpc_id)
    assert any(item["id"] == sg_id for item in listed)

    search = sg.search(sg_name)
    assert search is not None
    assert any(item["id"] == sg_id for item in search)

    sg.delete(sg_id)
    assert sg.details(sg_id) is None
