"""Tests for ``couchformation.aws.driver.image``."""

from __future__ import annotations

import pytest

from couchformation.aws.driver.base import AWSDriverError, EmptyResultSet
from couchformation.aws.driver.image import Image


@pytest.fixture
def image(aws_clients):
    return Image({})


def _make_image(
    image_id: str = "ami-1",
    name: str = "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-20240101",
    date: str = "2024-01-01T00:00:00.000Z",
    arch: str = "x86_64",
    owner_id: str = "099720109477",
    device: str = "/dev/sda1",
    platform: str = "Linux/UNIX",
):
    return {
        "ImageId": image_id,
        "Name": name,
        "CreationDate": date,
        "PlatformDetails": platform,
        "BlockDeviceMappings": [{"DeviceName": device}],
        "Architecture": arch,
        "OwnerId": owner_id,
    }


def test_list_private_images(image, aws_clients):
    aws_clients.get("ec2").describe_images.return_value = {
        "Images": [_make_image(image_id="ami-x", name="my-private")]
    }
    result = image.list()
    assert len(result) == 1
    assert result[0]["name"] == "ami-x"
    assert result[0]["description"] == "my-private"
    _, kwargs = aws_clients.get("ec2").describe_images.call_args
    assert kwargs["Filters"] == [{"Name": "is-public", "Values": ["false"]}]
    assert kwargs["Owners"] == []


def test_list_public_with_owner_and_name(image, aws_clients):
    aws_clients.get("ec2").describe_images.return_value = {
        "Images": [_make_image()]
    }
    result = image.list(is_public=True, owner_id="099720109477", name="pat*")
    assert result[0]["owner"] == "099720109477"
    _, kwargs = aws_clients.get("ec2").describe_images.call_args
    assert kwargs["Owners"] == ["099720109477"]
    names = [f["Name"] for f in kwargs["Filters"]]
    assert "name" in names
    assert "architecture" in names


def test_list_filter_keys_exist_match(image, aws_clients):
    aws_clients.get("ec2").describe_images.return_value = {
        "Images": [_make_image()]
    }
    result = image.list(filter_keys_exist=["name", "arch"])
    assert len(result) == 1


def test_list_filter_keys_exist_no_match_raises(image, aws_clients):
    aws_clients.get("ec2").describe_images.return_value = {
        "Images": [_make_image()]
    }
    with pytest.raises(EmptyResultSet):
        image.list(filter_keys_exist=["does_not_exist"])


def test_list_empty_raises(image, aws_clients):
    aws_clients.get("ec2").describe_images.return_value = {"Images": []}
    with pytest.raises(EmptyResultSet):
        image.list()


def test_list_error_raises(image, aws_clients):
    aws_clients.get("ec2").describe_images.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error getting AMIs"):
        image.list()


def test_image_user_known_id():
    assert Image.image_user("ubuntu") == "ubuntu"


def test_image_user_unknown_id_returns_none():
    assert Image.image_user("does-not-exist") is None


def test_details_returns_first_image(image, aws_clients):
    img = _make_image()
    aws_clients.get("ec2").describe_images.return_value = {"Images": [img]}
    result = image.details("ami-1")
    assert result is img


def test_details_error_raises(image, aws_clients):
    aws_clients.get("ec2").describe_images.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error getting AMI"):
        image.details("ami-1")


def test_instance_details_returns_first_instance(image, aws_clients):
    instance = {"InstanceId": "i-1", "BlockDeviceMappings": [{"DeviceName": "/dev/sda1"}]}
    aws_clients.get("ec2").describe_instances.return_value = {
        "Reservations": [{"Instances": [instance]}]
    }
    assert image.instance_details("i-1") is instance


def test_instance_details_error_raises(image, aws_clients):
    aws_clients.get("ec2").describe_instances.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error getting instance"):
        image.instance_details("i-1")


def test_create_happy_path(image, aws_clients, monkeypatch):
    ec2 = aws_clients.get("ec2")
    ec2.describe_instances.return_value = {
        "Reservations": [
            {"Instances": [{"BlockDeviceMappings": [{"DeviceName": "/dev/sda1"}]}]}
        ]
    }
    ec2.create_image.return_value = {"ImageId": "ami-new"}
    waiter = ec2.get_waiter.return_value

    result = image.create("my-image", "i-1")
    assert result == "ami-new"
    waiter.wait.assert_called_once_with(ImageIds=["ami-new"])

    _, kwargs = ec2.create_image.call_args
    assert kwargs["InstanceId"] == "i-1"
    assert kwargs["Name"] == "my-image"
    assert kwargs["Description"] == "couch-formation-image"
    assert kwargs["BlockDeviceMappings"][0]["DeviceName"] == "/dev/sda1"


def test_create_with_description(image, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_instances.return_value = {
        "Reservations": [
            {"Instances": [{"BlockDeviceMappings": [{"DeviceName": "/dev/sda1"}]}]}
        ]
    }
    ec2.create_image.return_value = {"ImageId": "ami-new"}
    image.create("my-image", "i-1", description="custom")
    _, kwargs = ec2.create_image.call_args
    assert kwargs["Description"] == "custom"


def test_create_missing_block_device_mapping_raises(image, aws_clients):
    aws_clients.get("ec2").describe_instances.return_value = {
        "Reservations": [{"Instances": [{}]}]
    }
    with pytest.raises(AWSDriverError, match="can not get details"):
        image.create("my-image", "i-1")


def test_create_instance_details_error_raises(image, aws_clients):
    aws_clients.get("ec2").describe_instances.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error getting instance"):
        image.create("my-image", "i-1")


def test_create_image_error_raises(image, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_instances.return_value = {
        "Reservations": [
            {"Instances": [{"BlockDeviceMappings": [{"DeviceName": "/dev/sda1"}]}]}
        ]
    }
    ec2.create_image.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error creating AMI"):
        image.create("my-image", "i-1")


def test_delete_deregisters(image, aws_clients):
    image.delete("ami-1")
    aws_clients.get("ec2").deregister_image.assert_called_once_with(ImageId="ami-1")


def test_delete_error_raises(image, aws_clients):
    aws_clients.get("ec2").deregister_image.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error deleting AMI"):
        image.delete("ami-1")


def test_list_standard_picks_latest_match(image, aws_clients, monkeypatch):
    """list_standard sorts filtered images by date and returns the newest."""
    import couchformation.aws.driver.image as image_mod

    monkeypatch.setattr(
        image_mod.AWSImageOwners,
        "image_owner_list",
        [
            {
                "owner_id": "owner-1",
                "description": "Ubuntu Linux",
                "os_id": "ubuntu",
                "user": "ubuntu",
                "feature": None,
                "pattern": r"ubuntu/images/hvm-ssd/ubuntu-*-server-*",
                "version": r"ubuntu/images/hvm-ssd/ubuntu-.*-(.+?)-.*-server-.*",
            }
        ],
    )
    monkeypatch.setattr(image_mod.C, "OS_VERSION_LIST", {"ubuntu": ["22.04"]})

    old = _make_image(
        image_id="ami-old",
        name="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-20230101",
        date="2023-01-01T00:00:00.000Z",
    )
    new = _make_image(
        image_id="ami-new",
        name="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-20240101",
        date="2024-01-01T00:00:00.000Z",
    )
    aws_clients.get("ec2").describe_images.return_value = {"Images": [old, new]}

    result = image.list_standard(architecture="x86_64")
    assert result["name"] == "ami-new"
    assert result["os_id"] == "ubuntu"
    assert result["os_version"] == "22.04"
    assert result["os_user"] == "ubuntu"
