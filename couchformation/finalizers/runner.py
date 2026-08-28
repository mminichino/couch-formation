from __future__ import annotations

import logging
from typing import Any, Optional, Protocol

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
        primary_node: Optional[NodeResult] = None,
    ) -> None:
        ...


class FinalizerRunner:
    def run(
        self,
        project: ProjectConfig,
        group_or_groups: NodeGroupConfig | list[tuple[NodeGroupConfig, list[NodeResult]]],
        nodes: list[NodeResult] | None = None,
        password: str = "",
    ) -> None:
        from couchformation.finalizers.couchbase import CouchbaseFinalizer
        from couchformation.finalizers.default import DefaultFinalizer

        registry: dict[str, Any] = {
            "default": DefaultFinalizer(),
            "couchbase": CouchbaseFinalizer(),
        }

        if isinstance(group_or_groups, list):
            deployed_list = group_or_groups
        else:
            deployed_list = [(group_or_groups, nodes or [])]

        if not deployed_list:
            return

        primary_node: Optional[NodeResult] = None
        primary_group: Optional[NodeGroupConfig] = None
        for group, node_list in deployed_list:
            for node in node_list:
                if group.group == 0 and node.number == 1:
                    primary_node = node
                    primary_group = group
                    break
            if primary_node:
                break

        if not primary_node and deployed_list and deployed_list[0][1]:
            primary_group = deployed_list[0][0]
            primary_node = deployed_list[0][1][0]

        used_finalizers: set[str] = set()

        for group, node_list in deployed_list:
            chain = ["default"]
            if group.finalizer and group.finalizer != "default":
                chain.append(group.finalizer)

            for finalizer_name in chain:
                used_finalizers.add(finalizer_name)

            for node in node_list:
                for name in chain:
                    finalizer = registry.get(name)
                    if not finalizer:
                        raise ValueError(f"Unknown finalizer: {name}")
                    logger.info(
                        f"Running finalizer {name} on {node.node_name or node.name} "
                        f"(group={group.group}, number={node.number})"
                    )
                    finalizer.run(
                        project=project,
                        group=group,
                        node=node,
                        password=password,
                        variables=group.variables or {},
                        primary_node=primary_node,
                    )

        if primary_node and primary_group:
            for name in ["couchbase"]:
                if name in used_finalizers:
                    finalizer = registry.get(name)
                    if hasattr(finalizer, "post_run"):
                        finalizer.post_run(
                            project=project,
                            primary_node=primary_node,
                            primary_group=primary_group,
                            password=password,
                            variables=primary_group.variables or {},
                        )
