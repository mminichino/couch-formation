"""Tests for ``couchformation.aws.driver.dns``."""

from __future__ import annotations

import pytest

from couchformation.aws.driver.base import AWSDriverError
from couchformation.aws.driver.dns import DNS
from tests.aws.driver.conftest import make_client_error


@pytest.fixture
def dns(aws_clients):
    return DNS({})


def test_create_public_hosted_zone(dns, aws_clients):
    dns_client = aws_clients.get("route53")
    dns_client.create_hosted_zone.return_value = {
        "HostedZone": {"Id": "/hostedzone/Z1"}
    }
    result = dns.create("example.com", region="us-east-1")
    assert result == "/hostedzone/Z1"
    args, kwargs = dns_client.create_hosted_zone.call_args
    assert kwargs["Name"] == "example.com"
    assert kwargs["HostedZoneConfig"] == {"PrivateZone": False}
    assert "CallerReference" in kwargs
    assert "VPC" not in kwargs


def test_create_private_hosted_zone(dns, aws_clients):
    dns_client = aws_clients.get("route53")
    dns_client.create_hosted_zone.return_value = {
        "HostedZone": {"Id": "/hostedzone/Z2"}
    }
    result = dns.create("internal.example.com", vpc_id="vpc-abc", region="us-east-1")
    assert result == "/hostedzone/Z2"
    _, kwargs = dns_client.create_hosted_zone.call_args
    assert kwargs["HostedZoneConfig"] == {"PrivateZone": True}
    assert kwargs["VPC"] == {"VPCRegion": "us-east-1", "VPCId": "vpc-abc"}


def test_create_returns_none_when_no_zone_returned(dns, aws_clients):
    aws_clients.get("route53").create_hosted_zone.return_value = {}
    assert dns.create("example.com", region="us-east-1") is None


def test_create_error_raises(dns, aws_clients):
    aws_clients.get("route53").create_hosted_zone.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error creating hosted domain"):
        dns.create("example.com", region="us-east-1")


def test_details_returns_hosted_zone(dns, aws_clients):
    aws_clients.get("route53").get_hosted_zone.return_value = {
        "HostedZone": {"Id": "Z1", "Name": "example.com."}
    }
    assert dns.details("Z1") == {"Id": "Z1", "Name": "example.com."}


def test_details_no_such_zone_returns_none(dns, aws_clients):
    aws_clients.get("route53").get_hosted_zone.side_effect = make_client_error(
        "NoSuchHostedZone"
    )
    assert dns.details("Z1") is None


def test_details_other_client_error_raises(dns, aws_clients):
    aws_clients.get("route53").get_hosted_zone.side_effect = make_client_error(
        "AccessDenied"
    )
    with pytest.raises(AWSDriverError, match="ClientError"):
        dns.details("Z1")


def test_details_unexpected_error_raises(dns, aws_clients):
    aws_clients.get("route53").get_hosted_zone.side_effect = ValueError("nope")
    with pytest.raises(AWSDriverError, match="error:"):
        dns.details("Z1")


def test_zone_id_finds_matching_public_zone(dns, aws_clients):
    aws_clients.get("route53").list_hosted_zones.return_value = {
        "HostedZones": [
            {
                "Id": "/hostedzone/Z_PRIV",
                "Name": "example.com.",
                "Config": {"PrivateZone": True},
            },
            {
                "Id": "/hostedzone/Z_PUB",
                "Name": "example.com.",
                "Config": {"PrivateZone": False},
            },
        ]
    }
    assert dns.zone_id("example.com") == "/hostedzone/Z_PUB"


def test_zone_id_no_match_returns_none(dns, aws_clients):
    aws_clients.get("route53").list_hosted_zones.return_value = {
        "HostedZones": [
            {
                "Id": "/hostedzone/X",
                "Name": "other.com.",
                "Config": {"PrivateZone": False},
            },
        ]
    }
    assert dns.zone_id("example.com") is None


def test_zone_id_no_such_zone_returns_none(dns, aws_clients):
    aws_clients.get("route53").list_hosted_zones.side_effect = (
        make_client_error("NoSuchHostedZone")
    )
    assert dns.zone_id("example.com") is None


def test_zone_id_other_error_raises(dns, aws_clients):
    aws_clients.get("route53").list_hosted_zones.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError):
        dns.zone_id("example.com")


def test_record_sets_returns_values(dns, aws_clients):
    aws_clients.get("route53").list_resource_record_sets.return_value = {
        "ResourceRecordSets": [
            {
                "Type": "NS",
                "ResourceRecords": [{"Value": "ns1.example.com"}],
            },
            {
                "Type": "A",
                "ResourceRecords": [
                    {"Value": "1.2.3.4"},
                    {"Value": "5.6.7.8"},
                ],
            },
        ]
    }
    assert dns.record_sets("Z1", "A") == ["1.2.3.4", "5.6.7.8"]


def test_record_sets_no_such_zone_returns_none(dns, aws_clients):
    aws_clients.get("route53").list_resource_record_sets.side_effect = (
        make_client_error("NoSuchHostedZone")
    )
    assert dns.record_sets("Z1", "A") is None


def test_record_sets_unexpected_error_raises(dns, aws_clients):
    aws_clients.get("route53").list_resource_record_sets.side_effect = (
        RuntimeError("x")
    )
    with pytest.raises(AWSDriverError):
        dns.record_sets("Z1", "A")


def test_delete_returns_status(dns, aws_clients):
    aws_clients.get("route53").delete_hosted_zone.return_value = {
        "ChangeInfo": {"Status": "PENDING"}
    }
    assert dns.delete("Z1") == "PENDING"


def test_delete_error_raises(dns, aws_clients):
    aws_clients.get("route53").delete_hosted_zone.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error deleting hosted domain"):
        dns.delete("Z1")


def test_add_record_builds_change_batch(dns, aws_clients):
    dns_client = aws_clients.get("route53")
    dns_client.change_resource_record_sets.return_value = {
        "ChangeInfo": {"Status": "PENDING"}
    }
    assert (
        dns.add_record("Z1", "host.example.com", ["1.2.3.4", "5.6.7.8"])
        == "PENDING"
    )
    _, kwargs = dns_client.change_resource_record_sets.call_args
    assert kwargs["HostedZoneId"] == "Z1"
    change = kwargs["ChangeBatch"]["Changes"][0]
    assert change["Action"] == "CREATE"
    assert change["ResourceRecordSet"]["Name"] == "host.example.com"
    assert change["ResourceRecordSet"]["Type"] == "A"
    assert change["ResourceRecordSet"]["TTL"] == 300
    assert change["ResourceRecordSet"]["ResourceRecords"] == [
        {"Value": "1.2.3.4"},
        {"Value": "5.6.7.8"},
    ]


def test_add_record_error_raises(dns, aws_clients):
    aws_clients.get("route53").change_resource_record_sets.side_effect = (
        RuntimeError("x")
    )
    with pytest.raises(AWSDriverError, match="error adding record"):
        dns.add_record("Z1", "host", ["1.2.3.4"])


def test_delete_record_builds_change_batch(dns, aws_clients):
    dns_client = aws_clients.get("route53")
    dns_client.change_resource_record_sets.return_value = {
        "ChangeInfo": {"Status": "INSYNC"}
    }
    assert (
        dns.delete_record(
            "Z1", "host.example.com", ["1.2.3.4"], record_type="CNAME", ttl=60
        )
        == "INSYNC"
    )
    _, kwargs = dns_client.change_resource_record_sets.call_args
    change = kwargs["ChangeBatch"]["Changes"][0]
    assert change["Action"] == "DELETE"
    assert change["ResourceRecordSet"]["Type"] == "CNAME"
    assert change["ResourceRecordSet"]["TTL"] == 60


def test_delete_record_error_raises(dns, aws_clients):
    aws_clients.get("route53").change_resource_record_sets.side_effect = (
        RuntimeError("x")
    )
    with pytest.raises(AWSDriverError, match="error deleting record"):
        dns.delete_record("Z1", "host", ["1.2.3.4"])


def test_list_associations_paginated(dns, aws_clients):
    dns_client = aws_clients.get("route53")
    dns_client.list_hosted_zones_by_vpc.side_effect = [
        {
            "HostedZoneSummaries": [{"HostedZoneId": "Z1"}],
            "NextToken": "abc",
        },
        {"HostedZoneSummaries": [{"HostedZoneId": "Z2"}]},
    ]
    result = dns.list_associations("vpc-1", "us-east-1")
    assert result == [{"HostedZoneId": "Z1"}, {"HostedZoneId": "Z2"}]
    assert dns_client.list_hosted_zones_by_vpc.call_count == 2


def test_list_associations_error_raises(dns, aws_clients):
    aws_clients.get("route53").list_hosted_zones_by_vpc.side_effect = (
        RuntimeError("x")
    )
    with pytest.raises(AWSDriverError, match="error getting VPC list"):
        dns.list_associations("vpc-1", "us-east-1")


def test_associate_when_not_yet_associated(dns, aws_clients):
    dns_client = aws_clients.get("route53")
    dns_client.list_hosted_zones_by_vpc.return_value = {
        "HostedZoneSummaries": []
    }
    dns_client.associate_vpc_with_hosted_zone.return_value = {
        "ChangeInfo": {"Status": "PENDING"}
    }
    assert dns.associate("Z1", "vpc-1", "us-east-1") == "PENDING"
    dns_client.associate_vpc_with_hosted_zone.assert_called_once_with(
        HostedZoneId="Z1", VPC={"VPCRegion": "us-east-1", "VPCId": "vpc-1"}
    )


def test_associate_returns_none_when_already_associated(dns, aws_clients):
    dns_client = aws_clients.get("route53")
    dns_client.list_hosted_zones_by_vpc.return_value = {
        "HostedZoneSummaries": [{"HostedZoneId": "Z1"}]
    }
    assert dns.associate("Z1", "vpc-1", "us-east-1") is None
    dns_client.associate_vpc_with_hosted_zone.assert_not_called()


def test_associate_error_raises(dns, aws_clients):
    dns_client = aws_clients.get("route53")
    dns_client.list_hosted_zones_by_vpc.return_value = {"HostedZoneSummaries": []}
    dns_client.associate_vpc_with_hosted_zone.side_effect = RuntimeError("x")
    with pytest.raises(AWSDriverError, match="error associating hosted zone"):
        dns.associate("Z1", "vpc-1", "us-east-1")


def test_disassociate_when_associated(dns, aws_clients):
    dns_client = aws_clients.get("route53")
    dns_client.list_hosted_zones_by_vpc.return_value = {
        "HostedZoneSummaries": [{"HostedZoneId": "Z1"}]
    }
    dns_client.disassociate_vpc_from_hosted_zone.return_value = {
        "ChangeInfo": {"Status": "PENDING"}
    }
    assert dns.disassociate("Z1", "vpc-1", "us-east-1") == "PENDING"


def test_disassociate_when_not_associated_returns_none(dns, aws_clients):
    dns_client = aws_clients.get("route53")
    dns_client.list_hosted_zones_by_vpc.return_value = {"HostedZoneSummaries": []}
    assert dns.disassociate("Z1", "vpc-1", "us-east-1") is None
    dns_client.disassociate_vpc_from_hosted_zone.assert_not_called()


def test_disassociate_no_such_zone_returns_none(dns, aws_clients):
    dns_client = aws_clients.get("route53")
    dns_client.list_hosted_zones_by_vpc.return_value = {
        "HostedZoneSummaries": [{"HostedZoneId": "Z1"}]
    }
    dns_client.disassociate_vpc_from_hosted_zone.side_effect = make_client_error(
        "NoSuchHostedZone"
    )
    assert dns.disassociate("Z1", "vpc-1", "us-east-1") is None


def test_disassociate_other_client_error_raises(dns, aws_clients):
    dns_client = aws_clients.get("route53")
    dns_client.list_hosted_zones_by_vpc.return_value = {
        "HostedZoneSummaries": [{"HostedZoneId": "Z1"}]
    }
    dns_client.disassociate_vpc_from_hosted_zone.side_effect = make_client_error(
        "AccessDenied"
    )
    with pytest.raises(AWSDriverError, match="ClientError"):
        dns.disassociate("Z1", "vpc-1", "us-east-1")
