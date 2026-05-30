from __future__ import annotations

import pytest

from couchformation.aws.driver.base import AWSDriverError, CloudBase, EmptyResultSet
from couchformation.aws.driver.regions import Regions

pytestmark = pytest.mark.cf_aws


def test_init_default_profile(aws_parameters):
    base = CloudBase(aws_parameters)
    assert base.parameters == aws_parameters
    assert base.zone_list == []
    assert base.ec2_client is not None
    assert base.s3_client is not None
    assert base.dns_client is not None
    assert base.sts_client is not None


def test_account_id_returns_sts_account(aws_parameters):
    base = CloudBase(aws_parameters)
    account_id = base.account_id
    assert account_id
    assert account_id.isdigit()
    assert len(account_id) == 12


def test_region_property_returns_session_region(aws_parameters):
    base = CloudBase(aws_parameters)
    assert base.region == aws_parameters["region"]


def test_test_session_success(aws_parameters):
    CloudBase(aws_parameters).test_session(region=aws_parameters["region"])


def test_credentials_returns_aws_model(aws_parameters):
    creds = CloudBase(aws_parameters).credentials()
    assert creds.access_key_id
    assert creds.secret_access_key


def test_get_auth_config():
    cfg = CloudBase.get_auth_config()
    assert cfg["AWS_ACCESS_KEY_ID"]
    assert cfg["AWS_SECRET_ACCESS_KEY"]


def test_tag_exists_true():
    tags = [{"Key": "Name", "Value": "n"}, {"Key": "Env", "Value": "p"}]
    assert CloudBase.tag_exists("Env", tags) is True


def test_tag_exists_false():
    tags = [{"Key": "Name", "Value": "n"}]
    assert CloudBase.tag_exists("Missing", tags) is False


def test_get_tag_returns_value():
    tags = [{"Key": "Name", "Value": "alpha"}, {"Key": "Env", "Value": "p"}]
    assert CloudBase.get_tag("Env", tags) == "p"


def test_get_all_regions_returns_names(aws_parameters):
    regions = Regions(aws_parameters)
    region_list = regions.get_all_regions()
    assert aws_parameters["region"] in region_list
    assert len(region_list) > 0


def test_zones_returns_sorted_unique(aws_parameters):
    base = CloudBase(aws_parameters)
    result = base.zones()
    assert result == sorted(set(result))
    assert len(result) > 0
    assert base.zone_list == result


def test_error_class_hierarchy():
    assert issubclass(AWSDriverError, Exception)
    assert issubclass(EmptyResultSet, Exception)
