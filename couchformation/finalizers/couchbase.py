from __future__ import annotations

import logging
from typing import Optional

from couchformation.finalizers.base import execute_node_command
from couchformation.models.cloud_ops import NodeResult
from couchformation.models.project import NodeGroupConfig, ProjectConfig

logger = logging.getLogger("couchformation.finalizers.couchbase")
logger.addHandler(logging.NullHandler())


class CouchbaseFinalizer:
    name = "couchbase"

    def run(
        self,
        project: ProjectConfig,
        group: NodeGroupConfig,
        node: NodeResult,
        password: str,
        variables: dict[str, str],
        primary_node: Optional[NodeResult] = None,
    ) -> None:
        version = variables.get("version") or variables.get("sw_version") or "latest"
        cluster_name = variables.get("cluster_name", project.name)
        data_path = variables.get("data_path", "/cbdata")
        services = group.services or variables.get("services") or "data,index,query,fts"
        if services == "default":
            services = "data,index,query,fts"
        availability_zone = node.zone or variables.get("availability_zone") or "default"

        commands = [
            f"sudo bundlemgr -b CBS -V {version}",
        ]

        is_primary = (
            (primary_node and (node.node_name == primary_node.node_name or node.private_ip == primary_node.private_ip))
            or (group.group == 0 and node.number == 1)
        )

        if is_primary:
            public_ip = node.public_ip or node.private_ip
            commands.append(
                f"sudo swmgr cluster --name {cluster_name} --password {password} "
                f"--ip-address {node.private_ip} --external-ip-address {public_ip} "
                f"--services {services} --server-group {availability_zone} --data-path {data_path} create"
            )
        else:
            primary_priv_ip = (primary_node.private_ip if primary_node else None) or variables.get("primary_ip") or node.private_ip
            public_ip = node.public_ip or node.private_ip
            commands.append(
                f"sudo swmgr cluster --password {password} --rally-ip-address {primary_priv_ip} "
                f"--ip-address {node.private_ip} --external-ip-address {public_ip} "
                f"--services {services} --server-group {availability_zone} --data-path {data_path} add"
            )

        for command in commands:
            execute_node_command(node, group, command, password=password, check=True)

    def post_run(
        self,
        project: ProjectConfig,
        primary_node: NodeResult,
        primary_group: NodeGroupConfig,
        password: str,
        variables: dict[str, str],
    ) -> None:
        logger.info(f"Running Couchbase rebalance on primary node {primary_node.node_name or primary_node.name}")
        command = f"sudo swmgr cluster --password {password} --rally-ip-address {primary_node.private_ip} rebalance"
        execute_node_command(primary_node, primary_group, command, password=password, check=True)
