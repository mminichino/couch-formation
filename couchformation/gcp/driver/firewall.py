##
##

import logging
import re
from typing import List, Union

from google.api_core import exceptions as gcp_exceptions
from google.cloud import compute_v1

from couchformation.gcp.driver.base import CloudBase, GCPDriverError, EmptyResultSet, resource_to_dict

logger = logging.getLogger('couchformation.gcp.driver.firewall')
logger.addHandler(logging.NullHandler())
logging.getLogger("google").setLevel(logging.ERROR)


class Firewall(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self) -> List[dict]:
        firewall_list = []

        try:
            for firewall in self.firewall_client.list(project=self.gcp_project):
                firewall_list.append(resource_to_dict(firewall))
        except Exception as err:
            raise GCPDriverError(f"error listing firewall rules: {err}")

        if len(firewall_list) == 0:
            raise EmptyResultSet("no firewalls found")
        return firewall_list

    def search(self, pattern: str) -> List[dict]:
        firewall_list = []
        for entry in self.list():
            if re.search(pattern, entry['name']):
                firewall_list.append(entry)
        return firewall_list

    def create_ingress(self, name: str, network: str, cidr: str, protocol: str = "tcp", ports: Union[List[str], None] = None, udp_ports: Union[List[str], None] = None) -> str:
        target_link = None
        allowed = [compute_v1.Allowed(IP_protocol=protocol)]
        if ports:
            allowed[0].ports = list(ports)
        if udp_ports:
            allowed.append(compute_v1.Allowed(IP_protocol="udp", ports=list(udp_ports)))
        firewall_body = compute_v1.Firewall(
            name=name,
            network=f"global/networks/{network}",
            description="Couch Formation generated firewall rule",
            source_ranges=[cidr],
            allowed=allowed,
        )
        try:
            operation = self.firewall_client.insert(
                project=self.gcp_project,
                firewall_resource=firewall_body,
            )
            result = self.wait_for_global_operation(operation.name)
            target_link = result.get('targetLink')
        except gcp_exceptions.AlreadyExists:
            pass
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not create firewall rule: {err}")
        except Exception as err:
            raise GCPDriverError(f"error creating firewall rule: {err}")

        return target_link

    def delete(self, firewall: str) -> None:
        try:
            operation = self.firewall_client.delete(project=self.gcp_project, firewall=firewall)
            self.wait_for_global_operation(operation.name)
        except gcp_exceptions.NotFound:
            pass
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not delete firewall rule: {err}")
        except Exception as err:
            raise GCPDriverError(f"error deleting firewall rule: {err}")

    def details(self, firewall: str) -> Union[dict, None]:
        try:
            result = self.firewall_client.get(project=self.gcp_project, firewall=firewall)
            return resource_to_dict(result)
        except gcp_exceptions.NotFound:
            return None
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not find firewall entry: {err}")
        except Exception as err:
            raise GCPDriverError(f"error getting firewall rule: {err}")
