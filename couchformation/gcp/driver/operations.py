##
##

import time

from google.protobuf.json_format import MessageToDict

from couchformation.exception import FatalError, NonFatalError


class GCPDriverError(FatalError):
    pass


class GCPDriverTransientError(NonFatalError):
    pass


class EmptyResultSet(NonFatalError):
    pass


def resource_to_dict(message) -> dict:
    if message is None:
        return {}
    if isinstance(message, dict):
        return message
    if hasattr(message, "_pb"):
        return MessageToDict(message._pb)
    return message


class GCPOperations:

    def wait_for_global_operation(self, operation: str) -> dict:
        while True:
            result = self.global_operations_client.get(
                project=self.gcp_project,
                operation=operation,
            )
            if result.status == "DONE":
                if result.error:
                    raise GCPDriverError(resource_to_dict(result.error))
                return resource_to_dict(result)
            time.sleep(1)

    def wait_for_regional_operation(self, operation: str) -> dict:
        while True:
            result = self.region_operations_client.get(
                project=self.gcp_project,
                region=self.gcp_region,
                operation=operation,
            )
            if result.status == "DONE":
                if result.error:
                    raise GCPDriverError(resource_to_dict(result.error))
                return resource_to_dict(result)
            time.sleep(1)

    def wait_for_zone_operation(self, operation: str, zone: str) -> dict:
        while True:
            result = self.zone_operations_client.get(
                project=self.gcp_project,
                zone=zone,
                operation=operation,
            )
            if result.status == "DONE":
                if result.error:
                    raise GCPDriverError(resource_to_dict(result.error))
                return resource_to_dict(result)
            time.sleep(1)
