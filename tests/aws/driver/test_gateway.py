from __future__ import annotations

import pytest

from couchformation.aws.driver.gateway import InternetGateway
from couchformation.aws.driver.network import Network
from tests.aws.driver.conftest import unique_name

pytestmark = [pytest.mark.driver, pytest.mark.cf_aws]



def test_gateway_create_details_delete(aws_parameters, cidr_util, cleanup):
    network = Network(aws_parameters)
    gateway = InternetGateway(aws_parameters)

    vpc_name = unique_name(f"{aws_parameters['project']}-vpc")
    ig_name = unique_name(f"{aws_parameters['project']}-igw")
    vpc_cidr = cidr_util.get_next_network()

    vpc_id = network.create(vpc_name, vpc_cidr)
    cleanup(lambda: network.delete(vpc_id))

    ig_id = gateway.create(ig_name, vpc_id, tags={"Environment": "pytest"})
    cleanup(lambda: gateway.delete(ig_id))

    details = gateway.details(ig_id)
    assert details is not None
    assert details["id"] == ig_id
    assert vpc_id in details["attachments"]

    listed = gateway.list()
    assert any(item["id"] == ig_id for item in listed)

    assert gateway.get(ig_name) == ig_id

    gateway.delete(ig_id)
    assert gateway.details(ig_id) is None
