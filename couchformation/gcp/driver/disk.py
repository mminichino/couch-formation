##
##

import json
import logging
from typing import List, Union

from google.api_core import exceptions as gcp_exceptions
from google.cloud.compute_v1.types import Disk

from couchformation.gcp.driver.base import CloudBase, GCPDriverError, EmptyResultSet, resource_to_dict

logger = logging.getLogger('couchformation.gcp.driver.disk')
logger.addHandler(logging.NullHandler())
logging.getLogger("google").setLevel(logging.ERROR)


class Disk(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self, zone: str) -> List[dict]:
        disk_list = []

        try:
            for disk in self.disk_client.list(project=self.gcp_project, zone=zone):
                disk_list.append(resource_to_dict(disk))
        except Exception as err:
            raise GCPDriverError(f"error listing disks: {err}")

        if len(disk_list) == 0:
            raise EmptyResultSet("no disks found")
        return disk_list

    def create(self, name: str, zone: str, size: str, disk_type: str = "pd-ssd") -> str:
        target_link = None
        disk_body = {
            "sizeGb": str(round(float(size))),
            "name": name,
            "type": f"zones/{zone}/diskTypes/{disk_type}",
        }
        try:
            operation = self.disk_client.insert(
                project=self.gcp_project,
                zone=zone,
                disk_resource=Disk.from_json(json.dumps(disk_body)),
            )
            result = self.wait_for_zone_operation(operation.name, zone)
            target_link = result.get('targetLink')
        except gcp_exceptions.AlreadyExists:
            pass
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not create disk: {err}")
        except Exception as err:
            raise GCPDriverError(f"error creating disk: {err}")

        return target_link

    def delete(self, disk: str, zone: str) -> None:
        try:
            operation = self.disk_client.delete(project=self.gcp_project, zone=zone, disk=disk)
            self.wait_for_zone_operation(operation.name, zone)
        except gcp_exceptions.NotFound:
            pass
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not delete disk: {err}")
        except Exception as err:
            raise GCPDriverError(f"error deleting disk: {err}")

    def details(self, disk: str, zone: str) -> Union[dict, None]:
        try:
            result = self.disk_client.get(project=self.gcp_project, zone=zone, disk=disk)
            return resource_to_dict(result)
        except gcp_exceptions.NotFound:
            return None
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not find disk: {err}")
        except Exception as err:
            raise GCPDriverError(f"error getting disk: {err}")

    def find(self, disk: str) -> Union[dict, None]:
        for zone in self.gcp_zone_list:
            result = self.details(disk, zone)
            if result:
                return result
        return None
