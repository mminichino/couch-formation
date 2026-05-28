##
##

import logging
import os
import configparser
from typing import Union, List
from azure.identity import AzureCliCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.dns import DnsManagementClient
from azure.mgmt.privatedns import PrivateDnsManagementClient
from azure.mgmt.resource.resources import ResourceManagementClient
from azure.mgmt.subscription import SubscriptionClient
from couchformation.exception import FatalError, NonFatalError
from couchformation.azure.driver.constants import get_auth_directory, get_config_default, get_config_main
from couchformation.azure.driver.constants import AzureDiskTiers
from couchformation.models.cloud_auth import AzureCredentials, CloudLoginParameters
from couchformation.models.public_cloud import PublicCloud

logger = logging.getLogger('couchformation.azure.driver.base')
logger.addHandler(logging.NullHandler())
logging.getLogger("azure").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class AzureDriverError(FatalError):
    pass


class EmptyResultSet(NonFatalError):
    pass


class CloudBase(PublicCloud):

    def __init__(self, parameters: dict | CloudLoginParameters | None = None):
        self.parameters: dict = {}
        self.auth_directory = get_auth_directory()
        self.config_default = get_config_default()
        self.config_main = get_config_main()
        self.cloud_name = 'AzureCloud'
        self.local_context = None
        self.azure_resource_group = None
        self.azure_location = None
        self.azure_availability_zones: list = []
        self.azure_zone = None
        self.credential = None
        self.azure_subscription_id = None
        self.azure_tenant_id = None
        self.subscription_client = None
        self.resource_client = None
        self.compute_client = None
        self.network_client = None
        self.dns_client = None
        self.private_dns_client = None

        if parameters is not None:
            login_params = CloudLoginParameters.from_parameters(parameters)
            self.parameters = login_params.model_dump(exclude_none=True)
            self.login(login_params)

    def login(self, parameters: CloudLoginParameters) -> None:
        self.parameters = parameters.model_dump(exclude_none=True)
        self.read_config()

        self.credential = AzureCliCredential(process_timeout=20)

        if not self.credential:
            raise AzureDriverError("unauthorized (use az login)")

        self.subscription_client = SubscriptionClient(self.credential)
        self.subscriptions = self.subscription_client.subscriptions.list()
        if not self.azure_subscription_id:
            self.azure_subscription_id = next(
                (str(s.subscription_id) for s in self.subscriptions),
                None,
            )
        self.azure_tenant_id = self.credential.tenant_id

        if not self.azure_subscription_id:
            raise AzureDriverError("no subscription found (use az account set --subscription <subscription_id>)")

        self.resource_client = ResourceManagementClient(self.credential, self.azure_subscription_id)
        self.compute_client = ComputeManagementClient(self.credential, self.azure_subscription_id)
        self.network_client = NetworkManagementClient(self.credential, self.azure_subscription_id)
        self.dns_client = DnsManagementClient(self.credential, self.azure_subscription_id)
        self.private_dns_client = PrivateDnsManagementClient(self.credential, self.azure_subscription_id)

        if parameters.region:
            self.set_region(parameters.region)
        elif self.parameters.get('region'):
            self.set_region(self.parameters['region'])

        if self.azure_location:
            self.zones()

    def test_session(self):
        if len(self.azure_availability_zones) == 0:
            raise AzureDriverError(f"Unable to determine availability zones for location {self.azure_location}")

    def credentials(self) -> AzureCredentials:
        return AzureCredentials(
            subscription_id=self.azure_subscription_id,
            tenant_id=self.azure_tenant_id,
        )

    @property
    def subscription_id(self):
        return self.azure_subscription_id

    @property
    def tenant_id(self):
        return self.azure_tenant_id

    @staticmethod
    def disk_size_to_tier(value: Union[int, str]):
        size = int(value)
        size_list = [int(i['disk_size']) for i in AzureDiskTiers.disk_tier_list]
        value = min([s for s in size_list if s >= size])
        return next(t for t in AzureDiskTiers.disk_tier_list if t['disk_size'] == str(value))

    @staticmethod
    def disk_caching(value: Union[int, str], ultra: bool = False):
        size = int(value)
        if size > 4095 or ultra:
            return "None"
        else:
            return "ReadWrite"

    def read_config(self):
        if os.path.exists(self.config_main):
            config = configparser.ConfigParser()
            try:
                config.read(self.config_main)
            except Exception as err:
                raise AzureDriverError(f"can not read config file {self.config_main}: {err}")

            if 'cloud' in config:
                if 'name' in config['cloud']:
                    self.cloud_name = config['cloud']['name']

            if 'local_context' in config:
                try:
                    self.local_context = list(config['local_context'].keys())[0]
                except IndexError:
                    pass

        if os.path.exists(self.config_default):
            config = configparser.ConfigParser()
            try:
                config.read(self.config_default)
            except Exception as err:
                raise AzureDriverError(f"can not read config file {self.config_default}: {err}")

            if self.cloud_name in config:
                self.azure_subscription_id = config[self.cloud_name].get('subscription', None)

    def zones(self) -> list:
        zone_list = self.compute_client.resource_skus.list(filter=f"location eq '{self.azure_location}'")
        for group in list(zone_list):
            if group.resource_type == 'virtualMachines':
                for resource_location in group.location_info:
                    for zone_number in resource_location.zones:
                        self.azure_availability_zones.append(zone_number)

        self.azure_availability_zones = sorted(set(self.azure_availability_zones))

        if len(self.azure_availability_zones) == 0:
            raise AzureDriverError("can not get Azure availability zones")

        self.azure_zone = self.azure_availability_zones[0]
        return self.azure_availability_zones

    def get_region(self) -> str | None:
        return self.azure_location

    def set_region(self, region: str) -> None:
        self.azure_location = region
        self.azure_availability_zones = []
        self.azure_zone = None

    @property
    def region(self):
        return self.get_region()

    def list_locations(self) -> List[dict]:
        location_list = []
        locations = self.subscription_client.subscriptions.list_locations(self.azure_subscription_id)
        for group in list(locations):
            location_block = {
                'name': group.name,
                'display_name': group.display_name
            }
            location_list.append(location_block)
        return location_list

    @staticmethod
    def process_tags(struct: dict) -> dict:
        block = {}
        if struct:
            for tag in struct:
                block.update({tag.lower() + '_tag': struct[tag]})
        block = dict(sorted(block.items()))
        return block
