"""Tests for ``couchformation.aws.driver.sshkey``."""

from __future__ import annotations

import pytest

from couchformation.aws.driver.base import AWSDriverError, EmptyResultSet
from couchformation.aws.driver.sshkey import SSHKey
from tests.aws.driver.conftest import make_client_error


@pytest.fixture
def ssh(aws_clients):
    return SSHKey({})


def _kp(name="k", kid="key-1", fp="fp:1", pubkey=None):
    entry = {"KeyName": name, "KeyPairId": kid, "KeyFingerprint": fp}
    if pubkey is not None:
        entry["PublicKey"] = pubkey
    return entry


def test_list_returns_blocks(ssh, aws_clients):
    aws_clients.get("ec2").describe_key_pairs.return_value = {
        "KeyPairs": [_kp("a"), _kp("b", "key-2", "fp:2", pubkey="ssh-rsa AAA")]
    }
    result = ssh.list()
    assert len(result) == 2
    assert result[0]["pubkey"] is None
    assert result[1]["pubkey"] == "ssh-rsa AAA"


def test_list_empty_raises(ssh, aws_clients):
    aws_clients.get("ec2").describe_key_pairs.return_value = {"KeyPairs": []}
    with pytest.raises(EmptyResultSet):
        ssh.list()


def test_list_error_raises(ssh, aws_clients):
    aws_clients.get("ec2").describe_key_pairs.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error getting key pairs"):
        ssh.list()


def test_list_filter_keys_exist(ssh, aws_clients):
    aws_clients.get("ec2").describe_key_pairs.return_value = {
        "KeyPairs": [_kp(), _kp("b", "key-2", "fp:2", pubkey="ssh-rsa AAA")]
    }
    result = ssh.list(filter_keys_exist=["fingerprint"])
    assert len(result) == 2


def test_create_imports_returns_name(ssh, aws_clients):
    aws_clients.get("ec2").import_key_pair.return_value = {
        "KeyName": "kp-new",
        "KeyPairId": "key-1",
        "KeyFingerprint": "fp",
    }
    result = ssh.create("kp-new", "ssh-rsa AAA")
    assert result == "kp-new"
    _, kwargs = aws_clients.get("ec2").import_key_pair.call_args
    assert kwargs["KeyName"] == "kp-new"
    assert kwargs["PublicKeyMaterial"] == b"ssh-rsa AAA"


def test_create_with_tags(ssh, aws_clients):
    aws_clients.get("ec2").import_key_pair.return_value = {
        "KeyName": "kp-new",
        "KeyPairId": "key-1",
        "KeyFingerprint": "fp",
    }
    ssh.create("kp-new", "ssh-rsa AAA", tags={"env": "p"})
    _, kwargs = aws_clients.get("ec2").import_key_pair.call_args
    tag_keys = {t["Key"] for t in kwargs["TagSpecifications"][0]["Tags"]}
    assert {"Name", "env"} <= tag_keys


def test_create_duplicate_falls_back_to_details(ssh, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.import_key_pair.side_effect = make_client_error("InvalidKeyPair.Duplicate")
    ec2.describe_key_pairs.return_value = {
        "KeyPairs": [_kp("existing-key", "key-2", "fp:2")]
    }
    result = ssh.create("existing-key", "ssh-rsa AAA")
    assert result == "existing-key"


def test_create_other_client_error_raises(ssh, aws_clients):
    aws_clients.get("ec2").import_key_pair.side_effect = make_client_error(
        "AccessDenied"
    )
    with pytest.raises(Exception):
        ssh.create("kp", "ssh-rsa AAA")


def test_create_native_returns_block(ssh, aws_clients):
    aws_clients.get("ec2").create_key_pair.return_value = {
        "KeyName": "kp",
        "KeyPairId": "key-1",
        "KeyFingerprint": "fp",
        "KeyMaterial": "----BEGIN----",
    }
    result = ssh.create_native("kp")
    assert result == {
        "name": "kp",
        "id": "key-1",
        "fingerprint": "fp",
        "key": "----BEGIN----",
    }


def test_details_returns_block(ssh, aws_clients):
    aws_clients.get("ec2").describe_key_pairs.return_value = {
        "KeyPairs": [_kp("kp", "key-1", "fp")]
    }
    assert ssh.details("kp") == {
        "name": "kp",
        "id": "key-1",
        "fingerprint": "fp",
    }


def test_details_index_error_returns_none(ssh, aws_clients):
    aws_clients.get("ec2").describe_key_pairs.return_value = {"KeyPairs": []}
    assert ssh.details("kp") is None


def test_details_not_found_returns_none(ssh, aws_clients):
    aws_clients.get("ec2").describe_key_pairs.side_effect = make_client_error(
        "InvalidKeyPair.NotFound"
    )
    assert ssh.details("kp") is None


def test_details_other_client_error_raises(ssh, aws_clients):
    aws_clients.get("ec2").describe_key_pairs.side_effect = make_client_error(
        "AccessDenied"
    )
    with pytest.raises(AWSDriverError, match="ClientError"):
        ssh.details("kp")


def test_delete_when_present(ssh, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_key_pairs.return_value = {"KeyPairs": [_kp("kp")]}
    ssh.delete("kp")
    ec2.delete_key_pair.assert_called_once_with(KeyName="kp")


def test_delete_when_missing_returns(ssh, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_key_pairs.return_value = {"KeyPairs": []}
    ssh.delete("kp")
    ec2.delete_key_pair.assert_not_called()


def test_delete_error_raises(ssh, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_key_pairs.return_value = {"KeyPairs": [_kp("kp")]}
    ec2.delete_key_pair.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error deleting key pair"):
        ssh.delete("kp")


def test_instances_by_key_paginates(ssh, aws_clients):
    ec2 = aws_clients.get("ec2")
    ec2.describe_instances.side_effect = [
        {
            "Reservations": [{"Instances": [{"InstanceId": "i-1"}]}],
            "NextToken": "n",
        },
        {"Reservations": [{"Instances": [{"InstanceId": "i-2"}]}]},
    ]
    instances = ssh.instances_by_key("kp")
    assert [i["InstanceId"] for i in instances] == ["i-1", "i-2"]
    _, kwargs = ec2.describe_instances.call_args_list[0]
    assert kwargs["Filters"][0]["Name"] == "key-name"
    assert kwargs["Filters"][0]["Values"] == ["kp"]


def test_instances_by_key_error_raises(ssh, aws_clients):
    aws_clients.get("ec2").describe_instances.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error getting instance list"):
        ssh.instances_by_key("kp")
