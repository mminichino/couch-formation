"""Tests for ``couchformation.aws.driver.network``."""

from __future__ import annotations

import pytest

from couchformation.aws.driver.base import AWSDriverError, EmptyResultSet
from couchformation.aws.driver.network import Network, Subnet
from tests.aws.driver.conftest import make_client_error


@pytest.fixture
def network(aws_clients):
    return Network({})


@pytest.fixture
def subnet(aws_clients):
    return Subnet({})


def _vpc(vpc_id="vpc-1", cidr="10.0.0.0/16", default=False, name=None):
    entry = {"VpcId": vpc_id, "CidrBlock": cidr, "IsDefault": default, "Tags": []}
    if name is not None:
        entry["Tags"] = [{"Key": "Name", "Value": name}]
    return entry


def test_network_list_paginates(network, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_vpcs.side_effect = [
        {"Vpcs": [_vpc("vpc-1")], "NextToken": "n"},
        {"Vpcs": [_vpc("vpc-2", "10.1.0.0/16", True)]},
    ]
    result = network.list()
    assert result == [
        {"cidr": "10.0.0.0/16", "default": False, "id": "vpc-1"},
        {"cidr": "10.1.0.0/16", "default": True, "id": "vpc-2"},
    ]


def test_network_list_filters_by_name(network, aws_clients):
    aws_clients.get("ec2").describe_vpcs.return_value = {
        "Vpcs": [_vpc("vpc-1", name="alpha"), _vpc("vpc-2", name="beta")]
    }
    result = network.list(name="beta")
    assert len(result) == 1
    assert result[0]["id"] == "vpc-2"


def test_network_list_returns_none_when_empty(network, aws_clients):
    aws_clients.get("ec2").describe_vpcs.return_value = {"Vpcs": []}
    assert network.list() is None


def test_network_list_error_raises(network, aws_clients):
    aws_clients.get("ec2").describe_vpcs.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error getting VPC list"):
        network.list()


def test_cidr_list_yields_cidrs(network, aws_clients):
    aws_clients.get("ec2").describe_vpcs.return_value = {
        "Vpcs": [_vpc("vpc-1", "10.0.0.0/16"), _vpc("vpc-2", "10.1.0.0/16")]
    }
    assert list(network.cidr_list) == ["10.0.0.0/16", "10.1.0.0/16"]


def test_network_create_returns_id(network, aws_clients):
    aws_clients.get("ec2").create_vpc.return_value = {"Vpc": {"VpcId": "vpc-x"}}
    assert network.create("v", "10.0.0.0/16", tags={"env": "p"}) == "vpc-x"
    _, kwargs = aws_clients.get("ec2").create_vpc.call_args
    tag_keys = {t["Key"] for t in kwargs["TagSpecifications"][0]["Tags"]}
    assert {"Name", "env"} <= tag_keys


def test_network_create_error_raises(network, aws_clients):
    aws_clients.get("ec2").create_vpc.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error creating VPC"):
        network.create("v", "10.0.0.0/16")


def test_enable_dns_hostnames(network, aws_clients):
    network.enable_dns_hostnames("vpc-1")
    aws_clients.get("ec2").modify_vpc_attribute.assert_called_once_with(
        VpcId="vpc-1", EnableDnsHostnames={"Value": True}
    )


def test_enable_dns_hostnames_error_raises(network, aws_clients):
    aws_clients.get("ec2").modify_vpc_attribute.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError):
        network.enable_dns_hostnames("vpc-1")


def test_network_delete_success(network, aws_clients):
    network.delete("vpc-1")
    aws_clients.get("ec2").delete_vpc.assert_called_once_with(VpcId="vpc-1")


def test_network_delete_not_found_returns(network, aws_clients):
    aws_clients.get("ec2").delete_vpc.side_effect = make_client_error(
        "InvalidVpcID.NotFound"
    )
    network.delete("vpc-1")


def test_network_delete_other_client_error_raises(network, aws_clients):
    aws_clients.get("ec2").delete_vpc.side_effect = make_client_error("AccessDenied")
    with pytest.raises(AWSDriverError, match="ClientError"):
        network.delete("vpc-1")


def test_network_delete_unexpected_error_raises(network, aws_clients):
    aws_clients.get("ec2").delete_vpc.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error deleting VPC"):
        network.delete("vpc-1")


def test_network_details_returns_block(network, aws_clients):
    aws_clients.get("ec2").describe_vpcs.return_value = {
        "Vpcs": [_vpc("vpc-1", "10.0.0.0/16", True)]
    }
    assert network.details("vpc-1") == {
        "cidr": "10.0.0.0/16",
        "default": True,
        "id": "vpc-1",
    }


def test_network_details_not_found_returns_none(network, aws_clients):
    aws_clients.get("ec2").describe_vpcs.side_effect = make_client_error(
        "InvalidVpcID.NotFound"
    )
    assert network.details("vpc-1") is None


def test_network_details_unexpected_error_raises(network, aws_clients):
    aws_clients.get("ec2").describe_vpcs.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError):
        network.details("vpc-1")


def _peer(pcx_id="pcx-1", cidr="10.0.0.0/16", status="active"):
    return {
        "VpcPeeringConnectionId": pcx_id,
        "RequesterVpcInfo": {"CidrBlock": cidr},
        "Status": {"Code": status},
    }


def test_peering_details_returns_blocks(network, aws_clients):
    aws_clients.get("ec2").describe_vpc_peering_connections.return_value = {
        "VpcPeeringConnections": [_peer("pcx-1"), _peer("pcx-2", "10.1.0.0/16")]
    }
    result = network.peering_details("vpc-1")
    assert [p["id"] for p in result] == ["pcx-1", "pcx-2"]


def test_peering_details_empty_returns_empty_list(network, aws_clients):
    aws_clients.get("ec2").describe_vpc_peering_connections.return_value = {
        "VpcPeeringConnections": []
    }
    assert network.peering_details("vpc-1") == []


def test_peering_details_error_raises(network, aws_clients):
    aws_clients.get("ec2").describe_vpc_peering_connections.side_effect = (
        RuntimeError("x")
    )
    with pytest.raises(AWSDriverError, match="error getting VPC list"):
        network.peering_details("vpc-1")


def test_peering_get_returns_block(network, aws_clients):
    aws_clients.get("ec2").describe_vpc_peering_connections.return_value = {
        "VpcPeeringConnections": [_peer("pcx-1")]
    }
    assert network.peering_get("pcx-1")["id"] == "pcx-1"


def test_peering_get_none_returns_none(network, aws_clients):
    aws_clients.get("ec2").describe_vpc_peering_connections.return_value = {
        "VpcPeeringConnections": []
    }
    assert network.peering_get("pcx-1") is None


def test_peering_get_not_found_returns_none(network, aws_clients):
    aws_clients.get("ec2").describe_vpc_peering_connections.side_effect = (
        make_client_error("InvalidVpcPeeringConnectionID.NotFound")
    )
    assert network.peering_get("pcx-1") is None


def test_peering_get_other_client_error_raises(network, aws_clients):
    aws_clients.get("ec2").describe_vpc_peering_connections.side_effect = (
        make_client_error("AccessDenied")
    )
    with pytest.raises(AWSDriverError, match="ClientError"):
        network.peering_get("pcx-1")


def test_peering_accept(network, aws_clients):
    network.peering_accept("pcx-1")
    aws_clients.get("ec2").accept_vpc_peering_connection.assert_called_once_with(
        VpcPeeringConnectionId="pcx-1"
    )


def test_peering_accept_client_error_raises(network, aws_clients):
    aws_clients.get("ec2").accept_vpc_peering_connection.side_effect = (
        make_client_error("InvalidStateTransition")
    )
    with pytest.raises(AWSDriverError, match="ClientError"):
        network.peering_accept("pcx-1")


def test_peering_accept_unexpected_error_raises(network, aws_clients):
    aws_clients.get("ec2").accept_vpc_peering_connection.side_effect = (
        RuntimeError("x")
    )
    with pytest.raises(AWSDriverError):
        network.peering_accept("pcx-1")


def test_peering_delete(network, aws_clients):
    network.peering_delete("pcx-1")
    aws_clients.get("ec2").delete_vpc_peering_connection.assert_called_once_with(
        VpcPeeringConnectionId="pcx-1"
    )


def test_peering_delete_client_error_raises(network, aws_clients):
    aws_clients.get("ec2").delete_vpc_peering_connection.side_effect = (
        make_client_error("InvalidVpcPeeringConnectionID.NotFound")
    )
    with pytest.raises(AWSDriverError, match="ClientError"):
        network.peering_delete("pcx-1")


def _subnet_entry(
    subnet_id="subnet-1",
    cidr="10.0.1.0/24",
    vpc_id="vpc-1",
    zone="us-east-1a",
    default=False,
    public=True,
):
    return {
        "SubnetId": subnet_id,
        "CidrBlock": cidr,
        "VpcId": vpc_id,
        "AvailabilityZone": zone,
        "DefaultForAz": default,
        "MapPublicIpOnLaunch": public,
    }


def test_subnet_list_paginates_and_filters(subnet, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_subnets.side_effect = [
        {"Subnets": [_subnet_entry("subnet-1")], "NextToken": "n"},
        {"Subnets": [_subnet_entry("subnet-2", zone="us-east-1b")]},
    ]
    result = subnet.list("vpc-1")
    assert [s["name"] for s in result] == ["subnet-1", "subnet-2"]


def test_subnet_list_with_zone_filter(subnet, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_subnets.return_value = {"Subnets": [_subnet_entry()]}
    subnet.list("vpc-1", zone="us-east-1a")
    _, kwargs = ec2.describe_subnets.call_args
    filters = kwargs["Filters"]
    assert any(
        f["Name"] == "availability-zone" and f["Values"] == ["us-east-1a"]
        for f in filters
    )


def test_subnet_list_filter_keys_exist(subnet, aws_clients):
    aws_clients.get("ec2").describe_subnets.return_value = {
        "Subnets": [_subnet_entry()]
    }
    result = subnet.list("vpc-1", filter_keys_exist=["cidr", "vpc"])
    assert len(result) == 1


def test_subnet_list_empty_raises(subnet, aws_clients):
    aws_clients.get("ec2").describe_subnets.return_value = {"Subnets": []}
    with pytest.raises(EmptyResultSet):
        subnet.list("vpc-1")


def test_subnet_list_error_raises(subnet, aws_clients):
    aws_clients.get("ec2").describe_subnets.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error getting subnets"):
        subnet.list("vpc-1")


def test_subnet_create_modifies_public_ip(subnet, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.create_subnet.return_value = {"Subnet": {"SubnetId": "subnet-new"}}
    result = subnet.create("name", "vpc-1", "us-east-1a", "10.0.1.0/24", tags={"k": "v"})
    assert result == "subnet-new"
    ec2.modify_subnet_attribute.assert_called_once_with(
        SubnetId="subnet-new", MapPublicIpOnLaunch={"Value": True}
    )


def test_subnet_details_returns_block(subnet, aws_clients):
    aws_clients.get("ec2").describe_subnets.return_value = {
        "Subnets": [_subnet_entry()]
    }
    result = subnet.details("subnet-1")
    assert result == {
        "cidr": "10.0.1.0/24",
        "name": "subnet-1",
        "vpc": "vpc-1",
        "zone": "us-east-1a",
        "default": False,
        "public": True,
    }


def test_subnet_details_index_error_returns_none(subnet, aws_clients):
    aws_clients.get("ec2").describe_subnets.return_value = {"Subnets": []}
    assert subnet.details("subnet-x") is None


def test_subnet_details_not_found_returns_none(subnet, aws_clients):
    aws_clients.get("ec2").describe_subnets.side_effect = make_client_error(
        "InvalidSubnetID.NotFound"
    )
    assert subnet.details("subnet-x") is None


def test_subnet_details_other_client_error_raises(subnet, aws_clients):
    aws_clients.get("ec2").describe_subnets.side_effect = make_client_error(
        "AccessDenied"
    )
    with pytest.raises(AWSDriverError, match="ClientError"):
        subnet.details("subnet-x")


def test_subnet_delete_success(subnet, aws_clients):
    subnet.delete("subnet-1")
    aws_clients.get("ec2").delete_subnet.assert_called_once_with(SubnetId="subnet-1")


def test_subnet_delete_not_found_returns(subnet, aws_clients):
    aws_clients.get("ec2").delete_subnet.side_effect = make_client_error(
        "InvalidSubnetID.NotFound"
    )
    subnet.delete("subnet-x")


def test_subnet_delete_unexpected_error_raises(subnet, aws_clients):
    aws_clients.get("ec2").delete_subnet.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error deleting subnet"):
        subnet.delete("subnet-x")
