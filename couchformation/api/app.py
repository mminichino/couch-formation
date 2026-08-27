from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from couchformation.models.project import (
    GroupCreateRequest,
    PeerConfigRequest,
    ProjectCreateRequest,
    ResourceCreateRequest,
)
from couchformation.resources.config_manager import ConfigurationManager
from couchformation.services.config import ProjectConfigService
from couchformation.services.deploy import ProjectDeployService
from couchformation.services.importer import ProjectImportService

security = HTTPBearer(auto_error=False)


class TokenRequest(BaseModel):
    token: Optional[str] = None


class GroupUpdateRequest(BaseModel):
    count: Optional[int] = None
    machine_type: Optional[str] = None
    finalizer: Optional[str] = None
    variables: dict[str, str] = Field(default_factory=dict)


class ResourceUpdateRequest(BaseModel):
    quantity: Optional[int] = None
    machine_type: Optional[str] = None
    region: Optional[str] = None


def _api_secret() -> str:
    return ConfigurationManager().ensure_api_token()


def create_access_token(subject: str = "cloudmgr", expires_minutes: int = 60 * 24) -> str:
    secret = _api_secret()
    payload = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = credentials.credentials
    secret = _api_secret()
    # Allow raw configured token or signed JWT using that token as secret
    if token == secret:
        return token
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload.get("sub", "cloudmgr")
    except jwt.PyJWTError as err:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {err}")


def create_app() -> FastAPI:
    app = FastAPI(title="Couch Formation API", version="5.0.0a1")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/auth/token")
    def issue_token(body: TokenRequest | None = None):
        if body and body.token:
            ConfigurationManager().ensure_api_token(body.token)
        return {"access_token": create_access_token(), "token_type": "bearer"}

    @app.post("/projects", dependencies=[Depends(require_auth)])
    def create_project(request: ProjectCreateRequest):
        return ProjectConfigService().create_project(request).model_dump()

    @app.get("/projects", dependencies=[Depends(require_auth)])
    def list_projects():
        return [p.model_dump(exclude={"password"}) for p in ProjectConfigService().list_projects()]

    @app.delete("/projects/{name_or_uuid}", dependencies=[Depends(require_auth)])
    def delete_project(name_or_uuid: str):
        ProjectConfigService().delete_project(name_or_uuid)
        return {"deleted": name_or_uuid}

    @app.get("/projects/{name_or_uuid}", dependencies=[Depends(require_auth)])
    def get_project(name_or_uuid: str):
        return ProjectDeployService().status(name_or_uuid)

    @app.post("/projects/{name_or_uuid}/groups", dependencies=[Depends(require_auth)])
    def create_group(name_or_uuid: str, request: GroupCreateRequest):
        return ProjectConfigService().create_group(name_or_uuid, request).model_dump()

    @app.get("/projects/{name_or_uuid}/groups", dependencies=[Depends(require_auth)])
    def list_groups(name_or_uuid: str):
        return [g.model_dump() for g in ProjectConfigService().list_groups(name_or_uuid)]

    @app.delete("/projects/{name_or_uuid}/groups/{group_number}", dependencies=[Depends(require_auth)])
    def remove_group(name_or_uuid: str, group_number: int):
        ProjectConfigService().remove_group(name_or_uuid, group_number)
        return {"removed": group_number}

    @app.patch("/projects/{name_or_uuid}/groups/{group_number}", dependencies=[Depends(require_auth)])
    def set_group(name_or_uuid: str, group_number: int, request: GroupUpdateRequest):
        return ProjectConfigService().set_group(name_or_uuid, group_number, request.model_dump(exclude_none=True)).model_dump()

    @app.post("/projects/{name_or_uuid}/resources", dependencies=[Depends(require_auth)])
    def create_resource(name_or_uuid: str, request: ResourceCreateRequest):
        return ProjectConfigService().create_resource(name_or_uuid, request).model_dump()

    @app.get("/projects/{name_or_uuid}/resources", dependencies=[Depends(require_auth)])
    def list_resources(name_or_uuid: str):
        return [r.model_dump() for r in ProjectConfigService().list_resources(name_or_uuid)]

    @app.delete("/projects/{name_or_uuid}/resources/{resource_name}", dependencies=[Depends(require_auth)])
    def remove_resource(name_or_uuid: str, resource_name: str):
        ProjectConfigService().remove_resource(name_or_uuid, resource_name)
        return {"removed": resource_name}

    @app.patch("/projects/{name_or_uuid}/resources/{resource_name}", dependencies=[Depends(require_auth)])
    def set_resource(name_or_uuid: str, resource_name: str, request: ResourceUpdateRequest):
        return ProjectConfigService().set_resource(name_or_uuid, resource_name, request.model_dump(exclude_none=True)).model_dump()

    @app.post("/projects/{name_or_uuid}/deploy", dependencies=[Depends(require_auth)])
    def deploy(name_or_uuid: str):
        return ProjectDeployService().deploy(name_or_uuid)

    @app.post("/projects/{name_or_uuid}/destroy", dependencies=[Depends(require_auth)])
    def destroy(name_or_uuid: str):
        return ProjectDeployService().destroy(name_or_uuid)

    @app.post("/projects/{name_or_uuid}/import", dependencies=[Depends(require_auth)])
    def import_project(name_or_uuid: str):
        return ProjectImportService().import_project(name_or_uuid)

    @app.post("/projects/{name_or_uuid}/peer", dependencies=[Depends(require_auth)])
    def peer(name_or_uuid: str, request: PeerConfigRequest):
        return ProjectDeployService().peer(name_or_uuid, request)

    return app
