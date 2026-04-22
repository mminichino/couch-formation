#

import logging
import boto3
import botocore.exceptions
import botocore.session
import os
from typing import Optional
from couchformation.aws.exceptions import AWSAuthException

logger = logging.getLogger('couchformation.aws.driver.auth')
logger.addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class AWSAuth(object):

    def __init__(self):
        self.zone_list = []

        if 'AWS_PROFILE' in os.environ:
            self.profile = os.environ['AWS_PROFILE']
        else:
            self.profile = 'default'

        try:
            session = boto3.Session()
            self.session = session
            self.ec2_client = session.client('ec2')
            self.s3_client = session.client('s3')
            self.dns_client = session.client('route53')
            self.sts_client = session.client('sts')
        except Exception as err:
            raise AWSAuthException(f"AWS: can not authenticate: {err}")

    @property
    def account_id(self):
        return self.sts_client.get_caller_identity()["Account"]

    def test_session(self, region: Optional[str] = None):
        try:
            if not region:
                region = self.session.region_name
            client = boto3.client('s3', region_name=region)
            client.list_buckets()
        except Exception as err:
            raise AWSAuthException(f"not authorized: {err}")

    @staticmethod
    def get_auth_config() -> dict:
        session = botocore.session.get_session()
        return {
            'AWS_ACCESS_KEY_ID': session.get_credentials().access_key,
            'AWS_SECRET_ACCESS_KEY': session.get_credentials().secret_key,
            'AWS_SESSION_TOKEN': session.get_credentials().token,
        }

    @property
    def region(self):
        return self.session.region_name

    def get_all_regions(self) -> list:
        regions = self.ec2_client.describe_regions(AllRegions=False)
        region_list = list(r['RegionName'] for r in regions['Regions'])
        return region_list

    def zones(self) -> list:
        try:
            zone_list = self.ec2_client.describe_availability_zones()
        except Exception as err:
            raise AWSAuthException(f"error getting availability zones: {err}")

        for availability_zone in zone_list['AvailabilityZones']:
            self.zone_list.append(availability_zone['ZoneName'])

        self.zone_list = sorted(set(self.zone_list))

        if len(self.zone_list) == 0:
            raise AWSAuthException("can not get AWS availability zones")

        return self.zone_list
