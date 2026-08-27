from __future__ import annotations

import logging

from couchformation.models.cloud_ops import ResourceRequest, ResourceResult

logger = logging.getLogger("couchformation.azure.resource")
logger.addHandler(logging.NullHandler())


class Resource:
    def create(self, request: ResourceRequest) -> ResourceResult:
        return ResourceResult(project=request.project, project_uuid=request.project_uuid, cloud="azure", name=request.name, created=False)

    def destroy(self, request: ResourceRequest) -> ResourceResult:
        return ResourceResult(project=request.project, project_uuid=request.project_uuid, cloud="azure", name=request.name, created=False)

    def import_resources(self, request: ResourceRequest) -> ResourceResult:
        return self.create(request)
