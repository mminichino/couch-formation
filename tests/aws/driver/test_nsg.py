"""Tests for ``couchformation.aws.driver.nsg``."""

from __future__ import annotations

import pytest

from couchformation.aws.driver.base import AWSDriverError, EmptyResultSet
from couchformation.aws.driver.nsg import SecurityGroup
from tests.aws.driver.conftest import make_client_error


@pytest.fixture
def sg(aws_clients):
    return SecurityGroup({})


def _sg_entry(
    sg_id="sg-1",
    name="grp",
    description="desc",
    vpc_id="vpc-1",
    tags=None,
):
    entry = {
        "GroupId": sg_id,
        "GroupName": name,
        "Description": description,
        "VpcId": vpc_id,
    }
    if tags is not None:
        entry["Tags"] = tags
    return entry


def test_list_paginates(sg, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_security_groups.side_effect = [
        {"SecurityGroups": [_sg_entry("sg-1")], "NextToken": "n"},
        {"SecurityGroups": [_sg_entry("sg-2")]},
    ]
    result = sg.list("vpc-1")
    assert [s["id"] for s in result] == ["sg-1", "sg-2"]


def test_list_empty_raises(sg, aws_clients):
    aws_clients.get("ec2").describe_security_groups.return_value = {
        "SecurityGroups": []
    }
    with pytest.raises(EmptyResultSet):
        sg.list("vpc-1")


def test_list_error_raises(sg, aws_clients):
    aws_clients.get("ec2").describe_security_groups.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error getting security groups"):
        sg.list("vpc-1")


def test_list_filter_keys_exist(sg, aws_clients):
    aws_clients.get("ec2").describe_security_groups.return_value = {
        "SecurityGroups": [_sg_entry()]
    }
    result = sg.list("vpc-1", filter_keys_exist=["name"])
    assert len(result) == 1


def test_create_returns_id(sg, aws_clients):
    aws_clients.get("ec2").create_security_group.return_value = {"GroupId": "sg-new"}
    assert sg.create("g", "desc", "vpc-1", tags={"env": "p"}) == "sg-new"
    _, kwargs = aws_clients.get("ec2").create_security_group.call_args
    tag_keys = {t["Key"] for t in kwargs["TagSpecifications"][0]["Tags"]}
    assert {"Name", "env"} <= tag_keys


def test_create_without_tags(sg, aws_clients):
    aws_clients.get("ec2").create_security_group.return_value = {"GroupId": "sg-new"}
    sg.create("g", "desc", "vpc-1")
    _, kwargs = aws_clients.get("ec2").create_security_group.call_args
    tag_keys = [t["Key"] for t in kwargs["TagSpecifications"][0]["Tags"]]
    assert tag_keys == ["Name"]


def test_create_error_raises(sg, aws_clients):
    aws_clients.get("ec2").create_security_group.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error creating security group"):
        sg.create("g", "d", "vpc-1")


def test_add_egress_returns_return(sg, aws_clients):
    aws_clients.get("ec2").authorize_security_group_egress.return_value = {
        "Return": True
    }
    assert sg.add_egress("sg-1", "tcp", 0, 65535, "0.0.0.0/0") is True


def test_add_egress_error_raises(sg, aws_clients):
    aws_clients.get("ec2").authorize_security_group_egress.side_effect = (
        RuntimeError("x")
    )
    with pytest.raises(AWSDriverError):
        sg.add_egress("sg-1", "tcp", 0, 65535, "0.0.0.0/0")


def test_add_ingress_returns_return(sg, aws_clients):
    aws_clients.get("ec2").authorize_security_group_ingress.return_value = {
        "Return": True
    }
    assert sg.add_ingress("sg-1", "tcp", 22, 22, "0.0.0.0/0") is True


def test_add_ingress_error_raises(sg, aws_clients):
    aws_clients.get("ec2").authorize_security_group_ingress.side_effect = (
        RuntimeError("x")
    )
    with pytest.raises(AWSDriverError):
        sg.add_ingress("sg-1", "tcp", 22, 22, "0.0.0.0/0")


def test_delete_calls_when_present(sg, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_security_groups.return_value = {
        "SecurityGroups": [_sg_entry("sg-1")]
    }
    sg.delete("sg-1")
    ec2.delete_security_group.assert_called_once_with(GroupId="sg-1")


def test_delete_when_missing_returns(sg, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_security_groups.return_value = {"SecurityGroups": []}
    sg.delete("sg-1")
    ec2.delete_security_group.assert_not_called()


def test_delete_error_raises(sg, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_security_groups.return_value = {
        "SecurityGroups": [_sg_entry("sg-1")]
    }
    ec2.delete_security_group.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error deleting security group"):
        sg.delete("sg-1")


def test_get_returns_id(sg, aws_clients):
    aws_clients.get("ec2").describe_security_groups.return_value = {
        "SecurityGroups": [_sg_entry("sg-1")]
    }
    assert sg.get("name") == "sg-1"


def test_get_empty_returns_none(sg, aws_clients):
    aws_clients.get("ec2").describe_security_groups.return_value = {
        "SecurityGroups": []
    }
    assert sg.get("name") is None


def test_get_not_found_returns_none(sg, aws_clients):
    aws_clients.get("ec2").describe_security_groups.side_effect = make_client_error(
        "InvalidGroup.NotFound"
    )
    assert sg.get("name") is None


def test_get_other_client_error_raises(sg, aws_clients):
    aws_clients.get("ec2").describe_security_groups.side_effect = make_client_error(
        "AccessDenied"
    )
    with pytest.raises(AWSDriverError, match="ClientError"):
        sg.get("name")


def test_search_returns_tag_dicts(sg, aws_clients):
    aws_clients.get("ec2").describe_security_groups.return_value = {
        "SecurityGroups": [
            _sg_entry(
                "sg-1",
                tags=[
                    {"Key": "Name", "Value": "grp"},
                    {"Key": "env", "Value": "p"},
                ],
            )
        ]
    }
    result = sg.search("grp")
    assert result == [{"Name": "grp", "env": "p", "id": "sg-1"}]


def test_search_not_found_returns_none(sg, aws_clients):
    aws_clients.get("ec2").describe_security_groups.side_effect = make_client_error(
        "InvalidGroup.NotFound"
    )
    assert sg.search("grp") is None


def test_details_returns_block(sg, aws_clients):
    aws_clients.get("ec2").describe_security_groups.return_value = {
        "SecurityGroups": [_sg_entry("sg-1")]
    }
    assert sg.details("sg-1") == {
        "name": "grp",
        "description": "desc",
        "id": "sg-1",
        "vpc": "vpc-1",
    }


def test_details_index_error_returns_none(sg, aws_clients):
    aws_clients.get("ec2").describe_security_groups.return_value = {
        "SecurityGroups": []
    }
    assert sg.details("sg-x") is None


def test_details_not_found_returns_none(sg, aws_clients):
    aws_clients.get("ec2").describe_security_groups.side_effect = make_client_error(
        "InvalidGroup.NotFound"
    )
    assert sg.details("sg-x") is None
