from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProjectModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class ProjectCreateRequest(ProjectModel):
    name: str
    region: Optional[str] = None
    cloud: Optional[str] = "aws"
    password: Optional[str] = None
    tags: Optional[list[str]] = None


class ProjectConfig(ProjectModel):
    name: str
    uuid: str
    region: Optional[str] = None
    cloud: Optional[str] = None
    password: Optional[str] = None


class GroupCreateRequest(ProjectModel):
    name: Optional[str] = None
    cloud: str = "aws"
    region: Optional[str] = None
    count: int = 1
    availability_zone: Optional[str] = None
    profile: Optional[str] = None
    build: str = "cbs"
    os_id: str = "ubuntu"
    os_version: str = "24.04"
    os_arch: str = "x86_64"
    machine_type: Optional[str] = "4x16"
    machine_name: Optional[str] = None
    services: Optional[str] = "default"
    volume_size: Optional[str] = "256"
    volume_iops: Optional[str] = None
    volume_type: Optional[str] = None
    volume_tier: Optional[str] = None
    root_size: Optional[str] = "256"
    ports: Optional[str] = None
    ssh_key: Optional[str] = None
    domain: Optional[str] = None
    cidr: Optional[str] = None
    allow: Optional[str] = "0.0.0.0/0"
    tags: Optional[str] = None
    ephemeral: bool = False
    finalizer: Optional[str] = None
    variables: dict[str, str] = Field(default_factory=dict)
    auth_mode: Optional[str] = None
    feature: Optional[str] = None
    sw_version: Optional[str] = None
    connect: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class NodeGroupConfig(ProjectModel):
    group: int
    name: str
    cloud: str
    region: Optional[str] = None
    count: int = 1
    availability_zone: Optional[str] = None
    profile: Optional[str] = None
    build: str = "cbs"
    os_id: Optional[str] = "ubuntu"
    os_version: Optional[str] = "24.04"
    os_arch: Optional[str] = "x86_64"
    machine_type: Optional[str] = "4x16"
    machine_name: Optional[str] = None
    services: Optional[str] = "default"
    volume_size: Optional[str] = "256"
    volume_iops: Optional[str] = None
    volume_type: Optional[str] = None
    volume_tier: Optional[str] = None
    root_size: Optional[str] = "256"
    ports: Optional[str] = None
    ssh_key: Optional[str] = None
    domain: Optional[str] = None
    cidr: Optional[str] = None
    allow: Optional[str] = "0.0.0.0/0"
    tags: Optional[str] = None
    ephemeral: bool = False
    finalizer: Optional[str] = None
    finalizer_group: Optional[int] = None
    variables: dict[str, str] = Field(default_factory=dict)
    auth_mode: Optional[str] = None
    feature: Optional[str] = None
    sw_version: Optional[str] = None
    connect: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class ResourceCreateRequest(ProjectModel):
    name: str
    cloud: str = "capella"
    region: Optional[str] = None
    build: Optional[str] = "capella"
    provider: Optional[str] = "aws"
    machine_type: Optional[str] = None
    quantity: int = 1
    cidr: Optional[str] = None
    allow: Optional[str] = "0.0.0.0/0"
    username: Optional[str] = "Administrator"
    password: Optional[str] = None
    sw_version: Optional[str] = "latest"
    type: Optional[str] = "database"
    peer_project: Optional[str] = None
    peer_region: Optional[str] = None
    profile: Optional[str] = "default"
    account_email: Optional[str] = None
    tags: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class ResourceConfig(ProjectModel):
    name: str
    cloud: str
    region: Optional[str] = None
    build: Optional[str] = None
    provider: Optional[str] = None
    machine_type: Optional[str] = None
    quantity: int = 1
    cidr: Optional[str] = None
    allow: Optional[str] = "0.0.0.0/0"
    username: Optional[str] = "Administrator"
    password: Optional[str] = None
    sw_version: Optional[str] = "latest"
    type: Optional[str] = "database"
    peer_project: Optional[str] = None
    peer_region: Optional[str] = None
    profile: Optional[str] = "default"
    account_email: Optional[str] = None
    tags: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class PeerConfigRequest(ProjectModel):
    provider_id: Optional[str] = None
    hosted_zone: Optional[str] = None
    peer_project: Optional[str] = None
    peer_region: Optional[str] = None
    cloud: Optional[str] = None
    region: Optional[str] = None
