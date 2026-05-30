##
##

import logging
from typing import Any

from couchformation.gcp.driver.base import CloudBase, GCPDriverError, EmptyResultSet, resource_to_dict
from couchformation.gcp.driver.constants import ComputeTypes
import couchformation.constants as C

logger = logging.getLogger('couchformation.gcp.driver.machine')
logger.addHandler(logging.NullHandler())
logging.getLogger("google").setLevel(logging.ERROR)


class MachineType(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self, zone: str, architecture: str = 'x86_64') -> list:
        machine_type_list = []
        if architecture == 'arm64':
            filter_string = 'cpuPlatform = "Ampere Altra"'
        else:
            filter_string = None

        try:
            request = {
                "project": self.gcp_project,
                "zone": zone,
            }
            if filter_string:
                request["filter"] = filter_string
            for machine_type in self.machine_type_client.list(
                request=request,
            ):
                machine_data = resource_to_dict(machine_type)
                if not machine_data['name'].startswith(tuple(ComputeTypes().as_list())):
                    continue
                config_block = {
                    'name': machine_data['name'],
                    'id': machine_data['id'],
                    'cpu': int(machine_data['guestCpus']),
                    'memory': int(machine_data['memoryMb']),
                    'description': machine_data['description'],
                }
                machine_type_list.append(config_block)
        except Exception as err:
            raise GCPDriverError(f"error listing machine types: {err}")

        if len(machine_type_list) == 0:
            raise EmptyResultSet("no instance types found")

        return machine_type_list

    def get_machine_types(self, zone: str, architecture: str = 'x86_64'):
        result_list = []
        machine_list = self.list(zone, architecture)
        machine_list = sorted(machine_list, key=lambda m: m['name'])

        for machine_type in C.MACHINE_TYPES:
            machine: dict[str, Any] | None = next((m for m in machine_list if m['cpu'] == machine_type['cpu'] and m['memory'] == machine_type['memory']), None)
            if not machine:
                continue
            machine.update(dict(machine_type=machine_type['name']))
            result_list.append(machine)

        return result_list

    def get_machine(self, name: str, zone: str, architecture: str = 'x86_64'):
        machine_list = self.get_machine_types(zone, architecture)
        return next((m for m in machine_list if m['machine_type'] == name), None)

    def details(self, machine_type: str) -> dict:
        try:
            response = self.machine_type_client.get(
                project=self.gcp_project,
                zone=self.gcp_zone,
                machine_type=machine_type,
            )
            machine_data = resource_to_dict(response)
            return {
                'name': machine_data['name'],
                'id': machine_data['id'],
                'cpu': int(machine_data['guestCpus']),
                'memory': int(machine_data['memoryMb']),
                'description': machine_data['description'],
            }
        except Exception as err:
            raise GCPDriverError(f"error getting machine type details: {err}")
