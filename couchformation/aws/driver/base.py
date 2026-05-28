##
##

import logging
import boto3
import os
import botocore
from typing import Optional

from couchformation.exception import FatalError, NonFatalError
from couchformation.models.cloud_auth import AWSCredentials, CloudLoginParameters
from couchformation.models.public_cloud import PublicCloud

logger = logging.getLogger('couchformation.aws.driver.base')
logger.addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class AWSDriverError(FatalError):
    pass


class EmptyResultSet(NonFatalError):
    pass


class CloudBase(PublicCloud):

    def __init__(self, parameters: dict | CloudLoginParameters | None = None):
        self.parameters: dict = {}
        self.zone_list: list = []
        self.profile = os.environ.get('AWS_PROFILE', 'default')
        self.session = None
        self.ec2_client = None
        self.s3_client = None
        self.dns_client = None
        self.sts_client = None

        if parameters is not None:
            login_params = CloudLoginParameters.from_parameters(parameters)
            self.parameters = login_params.model_dump(exclude_none=True)
            self.login(login_params)

    def login(self, parameters: CloudLoginParameters) -> None:
        self.parameters = parameters.model_dump(exclude_none=True)
        if parameters.profile:
            self.profile = parameters.profile
        elif 'AWS_PROFILE' in os.environ:
            self.profile = os.environ['AWS_PROFILE']
        else:
            self.profile = 'default'

        try:
            session_kwargs = {'profile_name': self.profile}
            if parameters.region:
                session_kwargs['region_name'] = parameters.region
            self.session = boto3.Session(**session_kwargs)
            self._init_clients()
        except Exception as err:
            raise AWSDriverError(f"AWS: can not authenticate: {err}")

    def _init_clients(self) -> None:
        self.ec2_client = self.session.client('ec2')
        self.s3_client = self.session.client('s3')
        self.dns_client = self.session.client('route53')
        self.sts_client = self.session.client('sts')

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
            raise AWSDriverError(f"not authorized: {err}")

    def credentials(self) -> AWSCredentials:
        creds = self.session.get_credentials()
        if not creds:
            session = botocore.session.get_session()
            creds = session.get_credentials()
        return AWSCredentials(
            access_key_id=creds.access_key if creds else None,
            secret_access_key=creds.secret_key if creds else None,
            session_token=creds.token if creds else None,
        )

    @staticmethod
    def get_auth_config() -> dict:
        session = botocore.session.get_session()
        creds = session.get_credentials()
        return {
            'AWS_ACCESS_KEY_ID': creds.access_key,
            'AWS_SECRET_ACCESS_KEY': creds.secret_key,
            'AWS_SESSION_TOKEN': creds.token,
        }

    def get_region(self) -> str | None:
        return self.session.region_name if self.session else None

    def set_region(self, region: str) -> None:
        self.session = boto3.Session(
            profile_name=self.profile,
            region_name=region,
        )
        self._init_clients()

    @property
    def region(self):
        return self.get_region()

    @staticmethod
    def tag_exists(key, tags):
        for i in range(len(tags)):
            if tags[i]['Key'] == key:
                return True
        return False

    @staticmethod
    def get_tag(key, tags):
        for i in range(len(tags)):
            if tags[i]['Key'] == key:
                return tags[i]['Value']
        return None

    def zones(self) -> list:
        try:
            zone_list = self.ec2_client.describe_availability_zones()
        except Exception as err:
            raise AWSDriverError(f"error getting availability zones: {err}")

        for availability_zone in zone_list['AvailabilityZones']:
            self.zone_list.append(availability_zone['ZoneName'])

        self.zone_list = sorted(set(self.zone_list))

        if len(self.zone_list) == 0:
            raise AWSDriverError("can not get AWS availability zones")

        return self.zone_list
