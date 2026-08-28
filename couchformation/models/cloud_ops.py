from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class CloudModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    def to_parameters(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class AuthRequest(CloudModel):
    cloud: str
    region: Optional[str] = None
    auth_mode: Optional[str] = None
    profile: Optional[str] = None
    project: Optional[str] = None


class AuthResult(CloudModel):
    cloud: str
    region: Optional[str] = None
    authenticated: bool = True
    credentials: Optional[dict[str, Any]] = None


class FoundationRequest(CloudModel):
    project: str
    project_uuid: str
    cloud: str
    region: str
    name: Optional[str] = "foundation"
    ssh_key: Optional[str] = None
    domain: Optional[str] = None
    cidr: Optional[str] = None
    tags: Optional[str] = None
    allow: Optional[str] = "0.0.0.0/0"
    auth_mode: Optional[str] = None
    profile: Optional[str] = None


class ZoneResult(CloudModel):
    zone: str
    cidr: Optional[str] = None
    subnet_id: Optional[str] = None
    subnet_name: Optional[str] = None


class FoundationResult(CloudModel):
    project: str
    project_uuid: str
    cloud: str
    region: str
    vpc_id: Optional[str] = None
    vpc_name: Optional[str] = None
    vpc_cidr: Optional[str] = None
    network_id: Optional[str] = None
    network_name: Optional[str] = None
    resource_group: Optional[str] = None
    security_group_id: Optional[str] = None
    ssh_key: Optional[str] = None
    internet_gateway_id: Optional[str] = None
    route_table_id: Optional[str] = None
    domain: Optional[str] = None
    public_hosted_zone: Optional[str] = None
    private_hosted_zone: Optional[str] = None
    zones: list[ZoneResult] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)


class NodeRequest(CloudModel):
    project: str
    project_uuid: str
    cloud: str
    region: str
    name: str
    group: int = 0
    number: int = 1
    build: Optional[str] = "cbs"
    zone: Optional[str] = None
    os_id: Optional[str] = "ubuntu"
    os_version: Optional[str] = "24.04"
    os_arch: Optional[str] = "x86_64"
    feature: Optional[str] = None
    machine_type: Optional[str] = "4x16"
    machine_name: Optional[str] = None
    quantity: Optional[int] = 1
    services: Optional[str] = "data,index,query,fts"
    volume_size: Optional[str] = "256"
    volume_iops: Optional[str] = None
    volume_type: Optional[str] = None
    volume_tier: Optional[str] = None
    root_size: Optional[str] = "256"
    ports: Optional[str] = None
    tags: Optional[str] = None
    allow: Optional[str] = "0.0.0.0/0"
    ssh_key: Optional[str] = None
    ephemeral: Optional[bool] = False
    auth_mode: Optional[str] = None
    profile: Optional[str] = None
    finalizer: Optional[str] = None
    variables: dict[str, str] = Field(default_factory=dict)


class NodeResult(CloudModel):
    project: str
    project_uuid: str
    cloud: str
    name: str
    group: int
    number: int
    node_name: Optional[str] = None
    instance_id: Optional[str] = None
    instance_name: Optional[str] = None
    public_ip: Optional[str] = None
    private_ip: Optional[str] = None
    zone: Optional[str] = None
    username: Optional[str] = None
    services: Optional[str] = None
    state: dict[str, Any] = Field(default_factory=dict)


class PeerRequest(CloudModel):
    project: str
    project_uuid: str
    cloud: str
    region: str
    provider_id: Optional[str] = None
    hosted_zone: Optional[str] = None
    peer_project: Optional[str] = None
    peer_region: Optional[str] = None
    auth_mode: Optional[str] = None
    profile: Optional[str] = None
    tags: Optional[str] = None


class PeerResult(CloudModel):
    project: str
    project_uuid: str
    cloud: str
    region: str
    peering_id: Optional[str] = None
    peer_cidr: Optional[str] = None
    peer_hosted_zone: Optional[str] = None
    accepted: bool = False
    state: dict[str, Any] = Field(default_factory=dict)


class ResourceRequest(CloudModel):
    project: str
    project_uuid: str
    cloud: str
    name: str
    region: Optional[str] = None
    build: Optional[str] = None
    provider: Optional[str] = None
    machine_type: Optional[str] = None
    quantity: Optional[int] = 1
    cidr: Optional[str] = None
    allow: Optional[str] = "0.0.0.0/0"
    username: Optional[str] = "Administrator"
    password: Optional[str] = None
    sw_version: Optional[str] = "latest"
    type: Optional[str] = "database"
    instance_id: Optional[str] = None
    instance_name: Optional[str] = None
    peer_project: Optional[str] = None
    peer_region: Optional[str] = None
    profile: Optional[str] = None
    account_email: Optional[str] = None
    tags: Optional[str] = None


class ResourceResult(CloudModel):
    project: str
    project_uuid: str
    cloud: str
    name: str
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    endpoint: Optional[str] = None
    created: bool = False
    state: dict[str, Any] = Field(default_factory=dict)
