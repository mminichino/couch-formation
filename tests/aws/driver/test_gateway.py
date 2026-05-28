"""Tests for ``couchformation.aws.driver.gateway``."""

from __future__ import annotations

import pytest

from couchformation.aws.driver.base import AWSDriverError, EmptyResultSet
from couchformation.aws.driver.gateway import InternetGateway
from tests.aws.driver.conftest import make_client_error


@pytest.fixture
def ig(aws_clients):
    return InternetGateway({})


def test_list_returns_blocks_and_paginates(ig, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_internet_gateways.side_effect = [
        {
            "InternetGateways": [
                {
                    "OwnerId": "111",
                    "Attachments": [{"VpcId": "vpc-1"}, {"VpcId": "vpc-2"}],
                    "InternetGatewayId": "igw-1",
                }
            ],
            "NextToken": "next",
        },
        {
            "InternetGateways": [
                {
                    "OwnerId": "222",
                    "Attachments": [],
                    "InternetGatewayId": "igw-2",
                }
            ]
        },
    ]
    result = ig.list()
    assert result == [
        {"owner": "111", "attachments": ["vpc-1", "vpc-2"], "id": "igw-1"},
        {"owner": "222", "attachments": [], "id": "igw-2"},
    ]
    assert ec2.describe_internet_gateways.call_count == 2


def test_list_empty_raises(ig, aws_clients):
    aws_clients.get("ec2").describe_internet_gateways.return_value = {
        "InternetGateways": []
    }
    with pytest.raises(EmptyResultSet):
        ig.list()


def test_list_error_raises(ig, aws_clients):
    aws_clients.get("ec2").describe_internet_gateways.side_effect = (
        RuntimeError("x")
    )
    with pytest.raises(AWSDriverError, match="Internet Gateway list"):
        ig.list()


def test_create_returns_id_and_attaches(ig, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.create_internet_gateway.return_value = {
        "InternetGateway": {"InternetGatewayId": "igw-new"}
    }
    result = ig.create("gw1", "vpc-1", tags={"env": "p"})
    assert result == "igw-new"
    ec2.attach_internet_gateway.assert_called_once_with(
        InternetGatewayId="igw-new", VpcId="vpc-1"
    )
    _, kwargs = ec2.create_internet_gateway.call_args
    tag_spec = kwargs["TagSpecifications"][0]
    assert tag_spec["ResourceType"] == "internet-gateway"
    tag_keys = {t["Key"] for t in tag_spec["Tags"]}
    assert {"Name", "env"} <= tag_keys


def test_create_without_tags(ig, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.create_internet_gateway.return_value = {
        "InternetGateway": {"InternetGatewayId": "igw-new"}
    }
    ig.create("gw1", "vpc-1")
    _, kwargs = ec2.create_internet_gateway.call_args
    tag_spec = kwargs["TagSpecifications"][0]
    tag_keys = [t["Key"] for t in tag_spec["Tags"]]
    assert tag_keys == ["Name"]


def test_create_error_raises(ig, aws_clients):
    aws_clients.get("ec2").create_internet_gateway.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error creating Internet Gateway"):
        ig.create("gw1", "vpc-1")


def test_delete_when_missing_returns(ig, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_internet_gateways.side_effect = IndexError
    ig.delete("igw-x")
    ec2.delete_internet_gateway.assert_not_called()


def test_delete_detaches_then_deletes(ig, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_internet_gateways.return_value = {
        "InternetGateways": [
            {
                "OwnerId": "111",
                "Attachments": [{"VpcId": "vpc-1"}, {"VpcId": "vpc-2"}],
                "InternetGatewayId": "igw-1",
            }
        ]
    }
    ig.delete("igw-1")
    assert ec2.detach_internet_gateway.call_count == 2
    ec2.delete_internet_gateway.assert_called_once_with(InternetGatewayId="igw-1")


def test_delete_error_raises(ig, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_internet_gateways.return_value = {
        "InternetGateways": [
            {"OwnerId": "1", "Attachments": [], "InternetGatewayId": "igw-1"}
        ]
    }
    ec2.delete_internet_gateway.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error deleting Internet Gateway"):
        ig.delete("igw-1")


def test_get_by_name_returns_id(ig, aws_clients):
    aws_clients.get("ec2").describe_internet_gateways.return_value = {
        "InternetGateways": [{"InternetGatewayId": "igw-1"}]
    }
    assert ig.get("name") == "igw-1"


def test_get_returns_none_on_empty(ig, aws_clients):
    aws_clients.get("ec2").describe_internet_gateways.return_value = {
        "InternetGateways": []
    }
    assert ig.get("name") is None


def test_get_not_found_error_returns_none(ig, aws_clients):
    aws_clients.get("ec2").describe_internet_gateways.side_effect = (
        make_client_error("InvalidInternetGatewayID.NotFound")
    )
    assert ig.get("name") is None


def test_get_other_client_error_raises(ig, aws_clients):
    aws_clients.get("ec2").describe_internet_gateways.side_effect = (
        make_client_error("AccessDenied")
    )
    with pytest.raises(AWSDriverError, match="ClientError"):
        ig.get("name")


def test_get_unexpected_error_raises(ig, aws_clients):
    aws_clients.get("ec2").describe_internet_gateways.side_effect = (
        RuntimeError("x")
    )
    with pytest.raises(AWSDriverError, match="error getting Internet Gateway"):
        ig.get("name")


def test_details_returns_block(ig, aws_clients):
    aws_clients.get("ec2").describe_internet_gateways.return_value = {
        "InternetGateways": [
            {
                "OwnerId": "111",
                "Attachments": [{"VpcId": "vpc-1"}],
                "InternetGatewayId": "igw-1",
            }
        ]
    }
    assert ig.details("igw-1") == {
        "owner": "111",
        "attachments": ["vpc-1"],
        "id": "igw-1",
    }


def test_details_not_found_returns_none(ig, aws_clients):
    aws_clients.get("ec2").describe_internet_gateways.side_effect = (
        make_client_error("InvalidInternetGatewayID.NotFound")
    )
    assert ig.details("igw-x") is None


def test_details_index_error_returns_none(ig, aws_clients):
    aws_clients.get("ec2").describe_internet_gateways.return_value = {
        "InternetGateways": []
    }
    assert ig.details("igw-x") is None
