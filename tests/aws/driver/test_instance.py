"""Tests for ``couchformation.aws.driver.instance``."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from couchformation.aws.driver.base import AWSDriverError
from couchformation.aws.driver.constants import PlacementType
from couchformation.aws.driver.instance import Instance, WIN_USER_DATA
from tests.aws.driver.conftest import make_client_error


@pytest.fixture
def instance(aws_clients):
    return Instance({})


def _ami_details(device: str = "/dev/sda1"):
    return {"BlockDeviceMappings": [{"DeviceName": device}]}


def test_run_zone_placement_default(instance, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_images.return_value = {"Images": [_ami_details()]}
    ec2.run_instances.return_value = {"Instances": [{"InstanceId": "i-1"}]}

    result = instance.run(
        name="node-1",
        ami="ami-1",
        ssh_key="key",
        sg_list="sg-1",
        subnet="subnet-1",
        zone="us-east-1a",
    )
    assert result == "i-1"
    _, kwargs = ec2.run_instances.call_args
    assert kwargs["Placement"] == {"AvailabilityZone": "us-east-1a"}
    assert kwargs["SecurityGroupIds"] == ["sg-1"]
    assert kwargs["SubnetId"] == "subnet-1"
    assert kwargs["ImageId"] == "ami-1"
    assert kwargs["KeyName"] == "key"
    assert "UserData" not in kwargs
    assert len(kwargs["BlockDeviceMappings"]) == 3
    ec2.get_waiter.assert_called_once_with("instance_running")


def test_run_host_placement(instance, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_images.return_value = {"Images": [_ami_details()]}
    ec2.run_instances.return_value = {"Instances": [{"InstanceId": "i-1"}]}
    instance.run(
        name="n",
        ami="ami-1",
        ssh_key="k",
        sg_list=["sg-1", "sg-2"],
        subnet="subnet-1",
        zone="zone-a",
        placement=PlacementType.HOST,
        host_id="h-1",
    )
    _, kwargs = ec2.run_instances.call_args
    assert kwargs["Placement"] == {"Tenancy": "host", "HostId": "h-1"}
    assert kwargs["SecurityGroupIds"] == ["sg-1", "sg-2"]


def test_run_winrm_userdata(instance, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_images.return_value = {"Images": [_ami_details()]}
    ec2.run_instances.return_value = {"Instances": [{"InstanceId": "i-1"}]}
    instance.run(
        name="n",
        ami="ami-1",
        ssh_key="k",
        sg_list="sg",
        subnet="s",
        zone="z",
        enable_winrm=True,
    )
    _, kwargs = ec2.run_instances.call_args
    assert kwargs["UserData"] == WIN_USER_DATA


def test_run_ephemeral_disk(instance, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_images.return_value = {"Images": [_ami_details()]}
    ec2.run_instances.return_value = {"Instances": [{"InstanceId": "i-1"}]}
    instance.run(
        name="n",
        ami="ami-1",
        ssh_key="k",
        sg_list="sg",
        subnet="s",
        zone="z",
        ephemeral=True,
    )
    _, kwargs = ec2.run_instances.call_args
    block_devices = kwargs["BlockDeviceMappings"]
    assert any("VirtualName" in d for d in block_devices)


def test_run_with_tags(instance, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_images.return_value = {"Images": [_ami_details()]}
    ec2.run_instances.return_value = {"Instances": [{"InstanceId": "i-1"}]}
    instance.run(
        name="n",
        ami="ami-1",
        ssh_key="k",
        sg_list="sg",
        subnet="s",
        zone="z",
        tags={"env": "prod"},
    )
    _, kwargs = ec2.run_instances.call_args
    tags = kwargs["TagSpecifications"][0]["Tags"]
    keys = {t["Key"] for t in tags}
    assert {"Name", "env"} <= keys


def test_run_missing_block_device_mapping_raises(instance, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_images.return_value = {"Images": [{}]}
    with pytest.raises(AWSDriverError, match="can not get details"):
        instance.run(
            name="n", ami="ami-1", ssh_key="k", sg_list="sg",
            subnet="s", zone="z",
        )


def test_run_image_details_error_raises(instance, aws_clients):
    aws_clients.get("ec2").describe_images.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error getting AMI"):
        instance.run(
            name="n", ami="ami-1", ssh_key="k", sg_list="sg",
            subnet="s", zone="z",
        )


def test_run_unexpected_error_raises(instance, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_images.return_value = {"Images": [_ami_details()]}
    ec2.run_instances.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error running instance"):
        instance.run(
            name="n", ami="ami-1", ssh_key="k", sg_list="sg",
            subnet="s", zone="z",
        )


def test_run_client_error_without_decode(instance, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_images.return_value = {"Images": [_ami_details()]}
    ec2.run_instances.side_effect = make_client_error("UnauthorizedOperation")
    with pytest.raises(AWSDriverError, match="AWS client error"):
        instance.run(
            name="n", ami="ami-1", ssh_key="k", sg_list="sg",
            subnet="s", zone="z",
        )


def test_list_paginates(instance, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_instances.side_effect = [
        {
            "Reservations": [{"Instances": [{"InstanceId": "i-1"}]}],
            "NextToken": "x",
        },
        {
            "Reservations": [
                {"Instances": [{"InstanceId": "i-2"}, {"InstanceId": "i-3"}]}
            ]
        },
    ]
    result = instance.list()
    assert [i["InstanceId"] for i in result] == ["i-1", "i-2", "i-3"]


def test_list_error_raises(instance, aws_clients):
    aws_clients.get("ec2").describe_instances.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error getting instance list"):
        instance.list()


def test_allocate_host_returns_id(instance, aws_clients):
    aws_clients.get("ec2").allocate_hosts.return_value = {"HostIds": ["h-1"]}
    assert instance.allocate_host("h", "us-east-1a", "mac2") == "h-1"


def test_allocate_host_error_raises(instance, aws_clients):
    aws_clients.get("ec2").allocate_hosts.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError):
        instance.allocate_host("h", "z", "t")


def _host(host_id="h-1", instance_ids=None, instance_type="mac2"):
    return {
        "HostId": host_id,
        "State": "available",
        "AllocationTime": datetime.now(timezone.utc) - timedelta(hours=2),
        "AvailabilityZone": "us-east-1a",
        "AvailableCapacity": {"AvailableVCpus": 8},
        "Instances": [{"InstanceId": i} for i in (instance_ids or [])],
        "HostProperties": {"InstanceType": instance_type},
    }


def test_list_hosts_no_filter(instance, aws_clients):
    aws_clients.get("ec2").describe_hosts.return_value = {
        "Hosts": [_host(instance_ids=["i-1"])]
    }
    result = instance.list_hosts()
    assert result[0]["id"] == "h-1"
    assert result[0]["instances"] == ["i-1"]
    assert result[0]["age"] >= 1
    _, kwargs = aws_clients.get("ec2").describe_hosts.call_args
    assert kwargs["Filters"] == []


def test_list_hosts_with_filter(instance, aws_clients):
    aws_clients.get("ec2").describe_hosts.return_value = {"Hosts": []}
    instance.list_hosts(instance_type="mac2")
    _, kwargs = aws_clients.get("ec2").describe_hosts.call_args
    assert kwargs["Filters"] == [{"Name": "instance-type", "Values": ["mac2"]}]


def test_list_hosts_error_raises(instance, aws_clients):
    aws_clients.get("ec2").describe_hosts.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError):
        instance.list_hosts()


def test_get_host_by_instance_found(instance, aws_clients):
    aws_clients.get("ec2").describe_hosts.return_value = {
        "Hosts": [_host(host_id="h-1", instance_ids=["i-1"])]
    }
    found = instance.get_host_by_instance("i-1")
    assert found["id"] == "h-1"


def test_get_host_by_instance_not_found(instance, aws_clients):
    aws_clients.get("ec2").describe_hosts.return_value = {"Hosts": []}
    assert instance.get_host_by_instance("i-1") is None


def test_get_host_by_id(instance, aws_clients):
    aws_clients.get("ec2").describe_hosts.return_value = {
        "Hosts": [_host(host_id="h-1")]
    }
    assert instance.get_host_by_id("h-1")["id"] == "h-1"
    assert instance.get_host_by_id("nope") is None


def test_release_host_success(instance, aws_clients):
    aws_clients.get("ec2").release_hosts.return_value = {"Unsuccessful": []}
    instance.release_host("h-1")
    aws_clients.get("ec2").release_hosts.assert_called_once_with(HostIds=["h-1"])


def test_release_host_unsuccessful_raises(instance, aws_clients):
    aws_clients.get("ec2").release_hosts.return_value = {
        "Unsuccessful": [{"Error": {"Message": "in use"}}]
    }
    with pytest.raises(AWSDriverError, match="Can not release host"):
        instance.release_host("h-1")


def test_release_host_error_raises(instance, aws_clients):
    aws_clients.get("ec2").release_hosts.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError):
        instance.release_host("h-1")


def test_details_returns_first(instance, aws_clients):
    aws_clients.get("ec2").describe_instances.return_value = {
        "Reservations": [{"Instances": [{"InstanceId": "i-1"}]}]
    }
    assert instance.details("i-1") == {"InstanceId": "i-1"}


def test_details_not_found_returns_none(instance, aws_clients):
    aws_clients.get("ec2").describe_instances.side_effect = make_client_error(
        "InvalidInstanceID.NotFound"
    )
    assert instance.details("i-1") is None


def test_details_index_error_returns_none(instance, aws_clients):
    aws_clients.get("ec2").describe_instances.return_value = {"Reservations": []}
    assert instance.details("i-1") is None


def test_details_other_client_error_raises(instance, aws_clients):
    aws_clients.get("ec2").describe_instances.side_effect = make_client_error(
        "AccessDenied"
    )
    with pytest.raises(AWSDriverError, match="ClientError"):
        instance.details("i-1")


def test_terminate_no_instance_returns(instance, aws_clients):
    aws_clients.get("ec2").describe_instances.return_value = {"Reservations": []}
    instance.terminate("i-1")
    aws_clients.get("ec2").terminate_instances.assert_not_called()


def test_terminate_runs_waiter(instance, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"InstanceId": "i-1"}]}]
    }
    instance.terminate("i-1")
    ec2.terminate_instances.assert_called_once_with(InstanceIds=["i-1"])
    ec2.get_waiter.assert_called_with("instance_terminated")


def test_terminate_error_raises(instance, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"InstanceId": "i-1"}]}]
    }
    ec2.terminate_instances.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error terminating instance"):
        instance.terminate("i-1")


def test_image_details_returns_first(instance, aws_clients):
    aws_clients.get("ec2").describe_images.return_value = {
        "Images": [{"ImageId": "ami-1"}]
    }
    assert instance.image_details("ami-1") == {"ImageId": "ami-1"}


def test_image_details_error_raises(instance, aws_clients):
    aws_clients.get("ec2").describe_images.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error getting AMI"):
        instance.image_details("ami-1")


def test_get_password_success(instance, aws_clients, monkeypatch):
    ec2 = aws_clients.get("ec2")
    encrypted = base64.b64encode(b"encrypted").decode("ascii")
    ec2.get_password_data.return_value = {"PasswordData": encrypted}

    import couchformation.aws.driver.instance as inst_mod

    ssh_util = MagicMock()
    ssh_util.return_value.decrypt_with_key.return_value = "secret"
    monkeypatch.setattr(inst_mod, "SSHUtil", ssh_util)

    assert instance.get_password("i-1", "key-material") == "secret"
    ssh_util.return_value.decrypt_with_key.assert_called_once_with(
        b"encrypted", "key-material"
    )


def test_get_password_waits_then_succeeds(instance, aws_clients, monkeypatch):
    ec2 = aws_clients.get("ec2")
    encrypted = base64.b64encode(b"data").decode("ascii")
    ec2.get_password_data.side_effect = [
        {"PasswordData": None},
        {"PasswordData": encrypted},
    ]

    import couchformation.aws.driver.instance as inst_mod

    monkeypatch.setattr(inst_mod.time, "sleep", lambda *_: None)

    ssh_util = MagicMock()
    ssh_util.return_value.decrypt_with_key.return_value = "pw"
    monkeypatch.setattr(inst_mod, "SSHUtil", ssh_util)

    assert instance.get_password("i-1", "key") == "pw"


def test_get_password_error_raises(instance, aws_clients):
    aws_clients.get("ec2").get_password_data.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error getting instance password"):
        instance.get_password("i-1", "key")
