from __future__ import annotations

import hashlib
from typing import Optional

from couchformation.identity.id import UniqueId


class ResourceName:
    @staticmethod
    def hex_from_uuid(project_uuid: str) -> str:
        return hashlib.md5(project_uuid.encode()).hexdigest()[:16]

    @classmethod
    def build(cls, prefix: str, project_uuid: str, index: int = 1) -> str:
        return f"{prefix}-{cls.hex_from_uuid(project_uuid)}-{index}"

    @staticmethod
    def new_project_id() -> UniqueId:
        return UniqueId()


def project_tag(project_uuid: str) -> dict[str, str]:
    return {"ProjectUUID": project_uuid, "ManagedBy": "couch-formation"}


def tags_to_csv(tags: dict[str, str], existing: Optional[str] = None) -> str:
    from couchformation.util import csv_dict_concat, parameter_to_dict

    merged = parameter_to_dict(existing) if existing else {}
    merged.update(tags)
    return ",".join(f"{k}:{v}" for k, v in merged.items())
