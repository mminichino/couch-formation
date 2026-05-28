"""Tests for ``couchformation.aws.driver.route``."""

from __future__ import annotations

import pytest

from couchformation.aws.driver.base import AWSDriverError
from couchformation.aws.driver.route import RouteTable
from tests.aws.driver.conftest import make_client_error


@pytest.fixture
def rt(aws_clients):
    return RouteTable({})


def _table(
    rt_id="rtb-1",
    vpc_id="vpc-1",
    owner="111",
    associations=None,
    routes=None,
):
    return {
        "RouteTableId": rt_id,
        "VpcId": vpc_id,
        "OwnerId": owner,
        "Associations": associations or [],
        "Routes": routes or [],
    }


def test_list_error_raises(rt, aws_clients):
    aws_clients.get("ec2").describe_route_tables.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError):
        rt.list()


def test_create_returns_id(rt, aws_clients):
    aws_clients.get("ec2").create_route_table.return_value = {
        "RouteTable": {"RouteTableId": "rtb-new"}
    }
    assert rt.create("name", "vpc-1", tags={"env": "p"}) == "rtb-new"
    _, kwargs = aws_clients.get("ec2").create_route_table.call_args
    tag_keys = {t["Key"] for t in kwargs["TagSpecifications"][0]["Tags"]}
    assert {"Name", "env"} <= tag_keys


def test_create_error_raises(rt, aws_clients):
    aws_clients.get("ec2").create_route_table.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error creating Route Table"):
        rt.create("n", "vpc-1")


def test_delete_when_present(rt, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_route_tables.return_value = {"RouteTables": [_table("rtb-1")]}
    rt.delete("rtb-1")
    ec2.delete_route_table.assert_called_once_with(RouteTableId="rtb-1")


def test_delete_when_missing_returns(rt, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_route_tables.return_value = {"RouteTables": []}
    rt.delete("rtb-1")
    ec2.delete_route_table.assert_not_called()


def test_delete_error_raises(rt, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_route_tables.return_value = {"RouteTables": [_table("rtb-1")]}
    ec2.delete_route_table.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error deleting Route Table"):
        rt.delete("rtb-1")


def test_get_returns_id(rt, aws_clients):
    aws_clients.get("ec2").describe_route_tables.return_value = {
        "RouteTables": [{"RouteTableId": "rtb-1"}]
    }
    assert rt.get("name") == "rtb-1"


def test_get_empty_returns_none(rt, aws_clients):
    aws_clients.get("ec2").describe_route_tables.return_value = {"RouteTables": []}
    assert rt.get("name") is None


def test_get_not_found_returns_none(rt, aws_clients):
    aws_clients.get("ec2").describe_route_tables.side_effect = make_client_error(
        "InvalidRouteTableID.NotFound"
    )
    assert rt.get("name") is None


def test_get_other_client_error_raises(rt, aws_clients):
    aws_clients.get("ec2").describe_route_tables.side_effect = make_client_error(
        "AccessDenied"
    )
    with pytest.raises(AWSDriverError, match="ClientError"):
        rt.get("name")


def test_details_returns_block(rt, aws_clients):
    aws_clients.get("ec2").describe_route_tables.return_value = {
        "RouteTables": [
            _table(
                "rtb-1",
                associations=[{"Main": True}],
                routes=[{"DestinationCidrBlock": "0.0.0.0/0"}],
            )
        ]
    }
    assert rt.details("rtb-1") == {
        "owner": "111",
        "associations": [{"Main": True}],
        "routes": [{"DestinationCidrBlock": "0.0.0.0/0"}],
        "vpc": "vpc-1",
        "id": "rtb-1",
    }


def test_details_index_error_returns_none(rt, aws_clients):
    aws_clients.get("ec2").describe_route_tables.return_value = {"RouteTables": []}
    assert rt.details("rtb-x") is None


def test_details_not_found_returns_none(rt, aws_clients):
    aws_clients.get("ec2").describe_route_tables.side_effect = make_client_error(
        "InvalidRouteTableID.NotFound"
    )
    assert rt.details("rtb-x") is None


def test_associate_returns_association_id(rt, aws_clients):
    aws_clients.get("ec2").associate_route_table.return_value = {
        "AssociationId": "rtbassoc-1"
    }
    assert rt.associate("rtb-1", "subnet-1") == "rtbassoc-1"


def test_associate_error_raises(rt, aws_clients):
    aws_clients.get("ec2").associate_route_table.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError):
        rt.associate("rtb-1", "subnet-1")


def test_add_route_returns_return(rt, aws_clients):
    aws_clients.get("ec2").create_route.return_value = {"Return": True}
    assert rt.add_route("0.0.0.0/0", "igw-1", "rtb-1") is True
    aws_clients.get("ec2").create_route.assert_called_once_with(
        DestinationCidrBlock="0.0.0.0/0", GatewayId="igw-1", RouteTableId="rtb-1"
    )


def test_add_route_error_raises(rt, aws_clients):
    aws_clients.get("ec2").create_route.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error creating route entry"):
        rt.add_route("0.0.0.0/0", "igw-1", "rtb-1")


def test_add_peer_route_returns_return(rt, aws_clients):
    aws_clients.get("ec2").create_route.return_value = {"Return": True}
    assert rt.add_peer_route("10.0.0.0/16", "pcx-1", "rtb-1") is True
    aws_clients.get("ec2").create_route.assert_called_once_with(
        DestinationCidrBlock="10.0.0.0/16",
        VpcPeeringConnectionId="pcx-1",
        RouteTableId="rtb-1",
    )


def test_add_peer_route_already_exists_returns_none(rt, aws_clients):
    aws_clients.get("ec2").create_route.side_effect = make_client_error(
        "RouteAlreadyExists"
    )
    assert rt.add_peer_route("10.0.0.0/16", "pcx-1", "rtb-1") is None


def test_add_peer_route_other_client_error_raises(rt, aws_clients):
    aws_clients.get("ec2").create_route.side_effect = make_client_error(
        "AccessDenied"
    )
    with pytest.raises(AWSDriverError, match="ClientError"):
        rt.add_peer_route("10.0.0.0/16", "pcx-1", "rtb-1")


def test_delete_route(rt, aws_clients):
    rt.delete_route("0.0.0.0/0", "rtb-1")
    aws_clients.get("ec2").delete_route.assert_called_once_with(
        DestinationCidrBlock="0.0.0.0/0", RouteTableId="rtb-1"
    )


def test_delete_route_not_found_returns(rt, aws_clients):
    aws_clients.get("ec2").delete_route.side_effect = make_client_error(
        "InvalidRoute.NotFound"
    )
    rt.delete_route("0.0.0.0/0", "rtb-1")


def test_delete_route_unexpected_error_raises(rt, aws_clients):
    aws_clients.get("ec2").delete_route.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error deleting route entry"):
        rt.delete_route("0.0.0.0/0", "rtb-1")
