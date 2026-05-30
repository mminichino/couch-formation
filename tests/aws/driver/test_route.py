from __future__ import annotations

import pytest

from couchformation.aws.driver.gateway import InternetGateway
from couchformation.aws.driver.network import Network
from couchformation.aws.driver.route import RouteTable
from tests.aws.driver.conftest import unique_name

pytestmark = pytest.mark.cf_aws


def test_route_table_create_add_route_delete(aws_parameters, cidr_util, cleanup):
    network = Network(aws_parameters)
    gateway = InternetGateway(aws_parameters)
    route = RouteTable(aws_parameters)

    vpc_name = unique_name(f"{aws_parameters['project']}-vpc")
    ig_name = unique_name(f"{aws_parameters['project']}-igw")
    rt_name = unique_name(f"{aws_parameters['project']}-rt")
    vpc_cidr = cidr_util.get_next_network()

    vpc_id = network.create(vpc_name, vpc_cidr)
    cleanup(lambda: network.delete(vpc_id))

    ig_id = gateway.create(ig_name, vpc_id)
    cleanup(lambda: gateway.delete(ig_id))

    rt_id = route.create(rt_name, vpc_id, tags={"Environment": "pytest"})
    cleanup(lambda: route.delete(rt_id))

    assert route.add_route("0.0.0.0/0", ig_id, rt_id) is True

    details = route.details(rt_id)
    assert details is not None
    assert details["id"] == rt_id
    assert any(r.get("DestinationCidrBlock") == "0.0.0.0/0" for r in details["routes"])

    route.delete_route("0.0.0.0/0", rt_id)
    route.delete(rt_id)
    assert route.details(rt_id) is None
