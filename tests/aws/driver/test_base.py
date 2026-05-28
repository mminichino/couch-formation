"""Tests for ``couchformation.aws.driver.base``."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from couchformation.aws.driver.base import (
    AWSDriverError,
    CloudBase,
    EmptyResultSet,
)
from couchformation.aws.driver.regions import Regions


def test_init_default_profile(monkeypatch, aws_clients):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    cb = CloudBase({"name": "test"})
    assert cb.profile == "default"
    assert cb.parameters == {"name": "test"}
    assert cb.zone_list == []
    assert cb.ec2_client is aws_clients.get("ec2")
    assert cb.s3_client is aws_clients.get("s3")
    assert cb.dns_client is aws_clients.get("route53")
    assert cb.sts_client is aws_clients.get("sts")


def test_init_uses_env_profile(monkeypatch, aws_clients):
    monkeypatch.setenv("AWS_PROFILE", "custom-profile")
    cb = CloudBase({})
    assert cb.profile == "custom-profile"


def test_init_authentication_failure(monkeypatch):
    import couchformation.aws.driver.base as base_mod

    def _raise(*a, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(base_mod.boto3, "Session", _raise)
    with pytest.raises(AWSDriverError, match="can not authenticate"):
        CloudBase({})


def test_account_id_returns_sts_account(cloud_base):
    cloud_base.sts_client.get_caller_identity.return_value = {
        "Account": "123456789012",
        "UserId": "AID",
        "Arn": "arn:aws:iam::123456789012:user/x",
    }
    assert cloud_base.account_id == "123456789012"
    cloud_base.sts_client.get_caller_identity.assert_called_once_with()


def test_region_property_returns_session_region(cloud_base):
    assert cloud_base.region == "us-east-1"


def test_test_session_success(monkeypatch, cloud_base):
    fake_s3 = MagicMock()
    captured = {}

    def _client(name, region_name=None):
        captured["name"] = name
        captured["region"] = region_name
        return fake_s3

    import couchformation.aws.driver.base as base_mod

    monkeypatch.setattr(base_mod.boto3, "client", _client)

    cloud_base.test_session(region="us-west-2")
    fake_s3.list_buckets.assert_called_once_with()
    assert captured == {"name": "s3", "region": "us-west-2"}


def test_test_session_uses_session_region_when_none(monkeypatch, cloud_base):
    fake_s3 = MagicMock()
    captured = {}

    def _client(name, region_name=None):
        captured["region"] = region_name
        return fake_s3

    import couchformation.aws.driver.base as base_mod

    monkeypatch.setattr(base_mod.boto3, "client", _client)

    cloud_base.test_session()
    assert captured["region"] == "us-east-1"


def test_test_session_failure(monkeypatch, cloud_base):
    fake_s3 = MagicMock()
    fake_s3.list_buckets.side_effect = RuntimeError("denied")

    import couchformation.aws.driver.base as base_mod

    monkeypatch.setattr(
        base_mod.boto3, "client", lambda *a, **kw: fake_s3
    )

    with pytest.raises(AWSDriverError, match="not authorized"):
        cloud_base.test_session("us-east-1")


def test_credentials_returns_aws_model(cloud_base):
    creds = MagicMock(access_key="AK", secret_key="SK", token="TOK")
    cloud_base.session.get_credentials.return_value = creds
    result = cloud_base.credentials()
    assert result.access_key_id == "AK"
    assert result.secret_access_key == "SK"
    assert result.session_token == "TOK"


def test_get_auth_config(monkeypatch):
    import couchformation.aws.driver.base as base_mod

    creds = MagicMock(access_key="AK", secret_key="SK", token="TOK")
    session = MagicMock()
    session.get_credentials.return_value = creds
    monkeypatch.setattr(
        base_mod.botocore.session, "get_session", lambda: session
    )

    cfg = CloudBase.get_auth_config()
    assert cfg == {
        "AWS_ACCESS_KEY_ID": "AK",
        "AWS_SECRET_ACCESS_KEY": "SK",
        "AWS_SESSION_TOKEN": "TOK",
    }


def test_tag_exists_true():
    tags = [{"Key": "Name", "Value": "n"}, {"Key": "Env", "Value": "p"}]
    assert CloudBase.tag_exists("Env", tags) is True


def test_tag_exists_false():
    tags = [{"Key": "Name", "Value": "n"}]
    assert CloudBase.tag_exists("Missing", tags) is False


def test_tag_exists_empty_list():
    assert CloudBase.tag_exists("Anything", []) is False


def test_get_tag_returns_value():
    tags = [{"Key": "Name", "Value": "alpha"}, {"Key": "Env", "Value": "p"}]
    assert CloudBase.get_tag("Env", tags) == "p"


def test_get_tag_missing_returns_none():
    tags = [{"Key": "Name", "Value": "alpha"}]
    assert CloudBase.get_tag("Missing", tags) is None


def test_get_all_regions_returns_names(cloud_base):
    cloud_base.ec2_client.describe_regions.return_value = {
        "Regions": [
            {"RegionName": "us-east-1"},
            {"RegionName": "us-west-2"},
            {"RegionName": "eu-west-1"},
        ]
    }
    regions = Regions()
    regions.session = cloud_base.session
    regions.ec2_client = cloud_base.ec2_client
    assert regions.get_all_regions() == [
        "us-east-1",
        "us-west-2",
        "eu-west-1",
    ]
    cloud_base.ec2_client.describe_regions.assert_called_once_with(
        AllRegions=False
    )


def test_zones_returns_sorted_unique(cloud_base):
    cloud_base.ec2_client.describe_availability_zones.return_value = {
        "AvailabilityZones": [
            {"ZoneName": "us-east-1b"},
            {"ZoneName": "us-east-1a"},
            {"ZoneName": "us-east-1a"},
        ]
    }
    result = cloud_base.zones()
    assert result == ["us-east-1a", "us-east-1b"]
    assert cloud_base.zone_list == ["us-east-1a", "us-east-1b"]


def test_zones_describe_failure_raises(cloud_base):
    cloud_base.ec2_client.describe_availability_zones.side_effect = (
        RuntimeError("oops")
    )
    with pytest.raises(AWSDriverError, match="error getting availability"):
        cloud_base.zones()


def test_zones_empty_raises(cloud_base):
    cloud_base.ec2_client.describe_availability_zones.return_value = {
        "AvailabilityZones": []
    }
    with pytest.raises(AWSDriverError, match="can not get AWS availability"):
        cloud_base.zones()


def test_error_class_hierarchy():
    assert issubclass(AWSDriverError, Exception)
    assert issubclass(EmptyResultSet, Exception)
