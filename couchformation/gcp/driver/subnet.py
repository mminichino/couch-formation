##
##

import logging
from typing import List, Union

from google.api_core import exceptions as gcp_exceptions
from google.cloud import compute_v1

from couchformation.gcp.driver.base import CloudBase, GCPDriverError, EmptyResultSet, resource_to_dict

logger = logging.getLogger('couchformation.gcp.driver.subnet')
logger.addHandler(logging.NullHandler())
logging.getLogger("google").setLevel(logging.ERROR)


class Subnet(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self, network: str, region: Union[str, None] = None) -> List[dict]:
        subnet_list = []

        try:
            for subnet in self.subnetwork_client.list(project=self.gcp_project, region=self.gcp_region):
                subnet_data = resource_to_dict(subnet)
                network_name = subnet_data['network'].rsplit('/', 1)[-1]
                region_name = subnet_data['region'].rsplit('/', 1)[-1]
                if region and region != region_name:
                    continue
                if network != network_name:
                    continue
                subnet_block = {
                    'cidr': subnet_data['ipCidrRange'],
                    'name': subnet_data['name'],
                    'description': subnet_data.get('description'),
                    'gateway': subnet_data['gatewayAddress'],
                    'network': network_name,
                    'region': region_name,
                    'id': subnet_data['id'],
                }
                subnet_list.append(subnet_block)
        except Exception as err:
            raise GCPDriverError(f"error listing subnets: {err}")

        if len(subnet_list) == 0:
            raise EmptyResultSet("no subnets found")
        return subnet_list

    def create(self, name: str, network: str, cidr: str) -> str | None:
        target_link = None
        network_result = self.network_client.get(project=self.gcp_project, network=network)
        network_info = resource_to_dict(network_result)
        subnetwork_body = compute_v1.Subnetwork(
            name=name,
            network=network_info['selfLink'],
            ip_cidr_range=cidr,
            region=self.gcp_region,
        )
        try:
            operation = self.subnetwork_client.insert(
                project=self.gcp_project,
                region=self.gcp_region,
                subnetwork_resource=subnetwork_body,
            )
            result = self.wait_for_regional_operation(operation.name)
            target_link = str(result.get('targetLink') or None)
        except gcp_exceptions.AlreadyExists:
            pass
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not create subnet: {err}")
        except Exception as err:
            raise GCPDriverError(f"error creating subnet: {err}")

        return target_link

    def delete(self, subnet: str) -> None:
        try:
            operation = self.subnetwork_client.delete(
                project=self.gcp_project,
                region=self.gcp_region,
                subnetwork=subnet,
            )
            self.wait_for_regional_operation(operation.name)
        except gcp_exceptions.NotFound:
            pass
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not delete subnet: {err}")
        except Exception as err:
            raise GCPDriverError(f"error deleting subnet: {err}")

    def details(self, subnet: str) -> Union[dict, None]:
        try:
            result = self.subnetwork_client.get(
                project=self.gcp_project,
                region=self.gcp_region,
                subnetwork=subnet,
            )
            subnet_data = resource_to_dict(result)
            network_name = subnet_data['network'].rsplit('/', 1)[-1]
            region_name = subnet_data['region'].rsplit('/', 1)[-1]
            return {
                'cidr': subnet_data['ipCidrRange'],
                'name': subnet_data['name'],
                'description': subnet_data.get('description'),
                'gateway': subnet_data['gatewayAddress'],
                'network': network_name,
                'region': region_name,
                'id': subnet_data['id'],
            }
        except gcp_exceptions.NotFound:
            return None
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not find subnet: {err}")
        except Exception as err:
            raise GCPDriverError(f"error getting subnet: {err}")
