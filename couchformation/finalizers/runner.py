from __future__ import annotations

import logging
from typing import Protocol

from couchformation.models.cloud_ops import NodeResult
from couchformation.models.project import NodeGroupConfig, ProjectConfig

logger = logging.getLogger("couchformation.finalizers")
logger.addHandler(logging.NullHandler())


class Finalizer(Protocol):
    name: str

    def run(
        self,
        project: ProjectConfig,
        group: NodeGroupConfig,
        node: NodeResult,
        password: str,
        variables: dict[str, str],
    ) -> None:
        ...


class FinalizerRunner:
    def run(
        self,
        project: ProjectConfig,
        group: NodeGroupConfig,
        nodes: list[NodeResult],
        password: str,
    ) -> None:
        from couchformation.finalizers.couchbase import CouchbaseFinalizer
        from couchformation.finalizers.default import DefaultFinalizer

        registry = {
            "default": DefaultFinalizer(),
            "couchbase": CouchbaseFinalizer(),
        }

        chain = ["default"]
        if group.finalizer and group.finalizer != "default":
            chain.append(group.finalizer)

        for node in nodes:
            for name in chain:
                finalizer = registry.get(name)
                if not finalizer:
                    raise ValueError(f"Unknown finalizer: {name}")
                logger.info(
                    f"Running finalizer {name} on {node.node_name or node.name} "
                    f"(finalizer_group={group.finalizer_group})"
                )
                finalizer.run(
                    project=project,
                    group=group,
                    node=node,
                    password=password,
                    variables=group.variables or {},
                )
