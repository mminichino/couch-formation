from typing import Union

from pydantic import BaseModel, ConfigDict


class CloudLoginParameters(BaseModel):
    model_config = ConfigDict(extra="allow")

    region: str | None = None
    auth_mode: str | None = None
    profile: str | None = None
    project: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "CloudLoginParameters":
        return cls.model_validate(data)

    @classmethod
    def from_parameters(cls, parameters) -> "CloudLoginParameters":
        if isinstance(parameters, cls):
            return parameters
        if isinstance(parameters, dict):
            return cls.from_dict(parameters)
        if hasattr(parameters, "as_dict"):
            return cls.from_dict(parameters.as_dict)
        raise TypeError(f"unsupported login parameters type: {type(parameters)!r}")


class AWSCredentials(BaseModel):
    access_key_id: str | None = None
    secret_access_key: str | None = None
    session_token: str | None = None


class GCPCredentials(BaseModel):
    account_email: str | None = None
    project_id: str | None = None
    project_number: str | None = None
    default_service_account: str | None = None


class AzureCredentials(BaseModel):
    subscription_id: str | None = None
    tenant_id: str | None = None


class CapellaCredentials(BaseModel):
    token: str | None = None
    user: str | None = None
    user_id: str | None = None
    project: str | None = None


CloudCredentials = Union[AWSCredentials, GCPCredentials, AzureCredentials, CapellaCredentials]
