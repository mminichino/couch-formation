from __future__ import annotations

import logging

from couchformation.aws.driver.base import CloudBase
from couchformation.models.cloud_auth import CloudLoginParameters
from couchformation.models.cloud_ops import AuthRequest, AuthResult

logger = logging.getLogger("couchformation.aws.auth")
logger.addHandler(logging.NullHandler())


class Auth:
    def configure(self, request: AuthRequest) -> AuthResult:
        params = CloudLoginParameters.from_dict(request.to_parameters())
        base = CloudBase()
        base.login(params)
        base.test_session()
        creds = base.credentials()
        return AuthResult(
            cloud="aws",
            region=base.get_region(),
            authenticated=True,
            credentials=creds.model_dump(exclude_none=True),
        )

    def login(self, request: AuthRequest) -> AuthResult:
        return self.configure(request)
