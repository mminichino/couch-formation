##
##

import logging

from typing import Any
from google.api_core import exceptions as gcp_exceptions
from google.cloud import dns
from google.cloud.dns.zone import ManagedZone

from couchformation.gcp.driver.base import CloudBase, GCPDriverError

logger = logging.getLogger('couchformation.gcp.driver.dns')
logger.addHandler(logging.NullHandler())
logging.getLogger("google").setLevel(logging.ERROR)


class DNS(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def fqdn(domain: str):
        if domain[-1] not in ['.']:
            domain = domain + '.'
        return domain

    def _dns_client(self, service_account: str | None = None) -> dns.Client:
        if service_account:
            return dns.Client(
                project=self.gcp_project,
                credentials=self.sa_auth(service_account),
            )
        return self.dns_client

    def create(self,
               domain: str,
               network_link: str | None = None,
               private: bool = False,
               peer_project: str | None = None,
               peer_network: str | None = None,
               service_account: str | None = None,
               zone_name: str | None = None):
        client = self._dns_client(service_account)

        if zone_name:
            name = zone_name
        else:
            name_part = domain.replace('.', '-')
            name = f"{name_part}-public" if not private else f"{name_part}-private"

        visibility = 'private' if private else 'public'

        dns_body: dict[str, Any] = {
            'name': name,
            'dnsName': self.fqdn(domain),
            'description': 'Couch Formation Managed Zone',
            'visibility': visibility,
        }

        if private and network_link:
            dns_body['privateVisibilityConfig'] = {
                'networks': [
                    {'networkUrl': network_link}
                ]
            }

        if peer_project and peer_network:
            dns_body['peeringConfig'] = {
                'targetNetwork': {
                    'networkUrl': (
                        f"https://www.googleapis.com/compute/v1/projects/"
                        f"{peer_project}/global/networks/{peer_network}"
                    ),
                }
            }

        try:
            zone = ManagedZone.from_api_repr(dns_body, client)
            zone.create(client=client)
            return name
        except gcp_exceptions.AlreadyExists:
            return name
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not create managed zone: {err}")
        except Exception as err:
            raise GCPDriverError(f"error creating managed zone: {err}")

    def details(self, name: str):
        try:
            zone: ManagedZone = self.dns_client.zone(name)
            if not zone.exists():
                return None
            zone.reload()
            return {
                'name': zone.name,
                'dnsName': zone.dns_name,
                'description': zone.description,
                'visibility': zone._properties.get("visibility"),
            }
        except gcp_exceptions.NotFound:
            return None
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not find managed zone: {err}")
        except Exception as err:
            raise GCPDriverError(f"error getting managed zone: {err}")

    def list_zones(self):
        zone_list = []
        try:
            for zone in self.dns_client.list_zones():
                zone_list.append({
                    'name': zone.name,
                    'dnsName': zone.dns_name,
                    'description': zone.description,
                    'visibility': zone._properties.get("visibility"),
                })
            return zone_list
        except Exception as err:
            raise GCPDriverError(f"error listing managed zones: {err}")

    def zone_name(self, domain: str):
        zones = self.list_zones()
        return next((zone['name'] for zone in zones if zone['dnsName'].startswith(domain)), None)

    def record_sets(self, name: str, r_type: str):
        record_list = []
        try:
            zone = self.dns_client.zone(name)
            for resource_record_set in zone.list_resource_record_sets():
                if resource_record_set.record_type != r_type:
                    continue
                record_list.extend(resource_record_set.rrdatas)
            return record_list
        except Exception as err:
            raise GCPDriverError(f"error listing managed zones: {err}")

    def delete(self, name: str, recursive: bool = False):
        try:
            zone = self.dns_client.zone(name)
            if recursive:
                changes = zone.changes()
                has_changes = False
                for resource_record_set in zone.list_resource_record_sets():
                    if resource_record_set.record_type in ('NS', 'SOA'):
                        continue
                    changes.delete_record_set(resource_record_set)
                    has_changes = True
                if has_changes:
                    changes.create()
            zone.delete()
        except gcp_exceptions.NotFound:
            pass
        except gcp_exceptions.GoogleAPICallError as err:
            raise GCPDriverError(f"can not delete managed zone: {err}")
        except Exception as err:
            raise GCPDriverError(f"error deleting managed zone: {err}")

    def add_record(self, managed_zone: str, name: str, values: list, record_type: str = 'A', ttl: int = 300):
        try:
            zone = self.dns_client.zone(managed_zone)
            record_set = zone.resource_record_set(
                name=self.fqdn(name),
                record_type=record_type,
                ttl=ttl,
                rrdatas=values,
            )
            changes = zone.changes()
            changes.add_record_set(record_set)
            changes.create()
        except Exception as err:
            raise GCPDriverError(f"error creating DNS records: {err}")

    def delete_record(self, managed_zone: str, name: str, record_type: str = 'A'):
        try:
            zone = self.dns_client.zone(managed_zone)
            record_set = zone.resource_record_set(
                name=self.fqdn(name),
                record_type=record_type,
                ttl=300,
                rrdatas=[],
            )
            changes = zone.changes()
            changes.delete_record_set(record_set)
            changes.create()
        except Exception as err:
            raise GCPDriverError(f"error deleting DNS records: {err}")
