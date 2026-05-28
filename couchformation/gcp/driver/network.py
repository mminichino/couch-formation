##
##

import logging
from typing import List, Union

from google.api_core import exceptions as gcp_exceptions
from google.cloud import compute_v1

from couchformation.gcp.driver.base import CloudBase, GCPDriverError, EmptyResultSet, resource_to_dict
from couchformation.gcp.driver.subnet import Subnet

logger = logging.getLogger('couchformation.gcp.driver.network')
logger.addHandler(logging.NullHandler())
logging.getLogger("google").setLevel(logging.ERROR)


class Network(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self) -> List[dict]:
        network_list = []

        try:
            for network in self.network_client.list(project=self.gcp_project):
                network_data = resource_to_dict(network)
                subnet_list = []
                for subnet in network_data.get('subnetworks', []):
                    subnet_name = subnet.rsplit('/', 4)[-1]
                    region_name = subnet.rsplit('/', 4)[-3]
                    if region_name != self.region:
                        continue
                    result = Subnet(self.parameters).details(subnet_name)
                    subnet_list.append(result)
                network_block = {
                    'cidr': network_data.get('IPv4Range'),
                    'name': network_data['name'],
                    'description': network_data.get('description'),
                    'subnets': subnet_list,
                    'id': network_data['id'],
                }
                network_list.append(network_block)
        except Exception as err:
            raise GCPDriverError(f"error listing networks: {err}")

        if len(network_list) == 0:
            raise EmptyResultSet("no networks found")
        return network_list

    @property
    def cidr_list(self):
        try:
            for network in self.list():
                for item in Subnet(self.parameters).list(network['name']):
                    yield item['cidr']
        except EmptyResultSet:
            return iter(())

    def create(self, name: str) -> str:
        target_link = None
        try:
            operation = self.network_client.insert(
                project=self.gcp_project,
                network_resource=compute_v1.Network(name=name, auto_create_subnetworks=False),
            )
            result = self.wait_for_global_operation(operation.name)
            target_link = result.get('targetLink')
            return target_link
        except gcp_exceptions.AlreadyExists:
            pass
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not create network: {err}")
        except Exception as err:
            raise GCPDriverError(f"error creating network: {err}")

        return target_link

    def delete(self, network: str) -> None:
        try:
            operation = self.network_client.delete(project=self.gcp_project, network=network)
            self.wait_for_global_operation(operation.name)
        except gcp_exceptions.NotFound:
            pass
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not delete network: {err}")
        except Exception as err:
            raise GCPDriverError(f"error deleting network: {err}")

    def details(self, network: str) -> Union[dict, None]:
        try:
            result = self.network_client.get(project=self.gcp_project, network=network)
            return resource_to_dict(result)
        except gcp_exceptions.NotFound:
            return None
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not find network: {err}")
        except Exception as err:
            raise GCPDriverError(f"error getting network: {err}")

    def add_peering(self, name: str, network: str, peer_project: str, peer_network: str) -> None:
        peering_body = compute_v1.NetworksAddPeeringRequest(
            network_peering=compute_v1.NetworkPeering(
                name=name,
                network=f"projects/{peer_project}/global/networks/{peer_network}",
                exchange_subnet_routes=True,
            )
        )
        try:
            operation = self.network_client.add_peering(
                project=self.gcp_project,
                network=network,
                networks_add_peering_request_resource=peering_body,
            )
            self.wait_for_global_operation(operation.name)
        except gcp_exceptions.AlreadyExists:
            pass
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not add network peering: {err}")
        except Exception as err:
            raise GCPDriverError(f"error adding network peering: {err}")

    def remove_peering(self, name: str, network: str) -> None:
        remove_body = compute_v1.NetworksRemovePeeringRequest(name=name)
        try:
            operation = self.network_client.remove_peering(
                project=self.gcp_project,
                network=network,
                networks_remove_peering_request_resource=remove_body,
            )
            self.wait_for_global_operation(operation.name)
        except gcp_exceptions.NotFound:
            pass
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not remove network peering: {err}")
        except Exception as err:
            raise GCPDriverError(f"error removing network peering: {err}")
