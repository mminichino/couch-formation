from __future__ import annotations

import logging

from couchformation.models.cloud_ops import ResourceRequest, ResourceResult

logger = logging.getLogger("couchformation.aws.resource")
logger.addHandler(logging.NullHandler())


class Resource:
    def create(self, request: ResourceRequest) -> ResourceResult:
        logger.debug("AWS resource create is a no-op")
        return ResourceResult(
            project=request.project,
            project_uuid=request.project_uuid,
            cloud="aws",
            name=request.name,
            created=False,
        )

    def destroy(self, request: ResourceRequest) -> ResourceResult:
        logger.debug("AWS resource destroy is a no-op")
        return ResourceResult(
            project=request.project,
            project_uuid=request.project_uuid,
            cloud="aws",
            name=request.name,
            created=False,
        )

    def import_resources(self, request: ResourceRequest) -> ResourceResult:
        return self.create(request)
