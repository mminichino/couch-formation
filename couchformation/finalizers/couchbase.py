from __future__ import annotations

import logging

from couchformation.finalizers.default import DefaultFinalizer
from couchformation.models.cloud_ops import NodeResult
from couchformation.models.project import NodeGroupConfig, ProjectConfig
from couchformation.provisioner.ssh import RunSSHCommand
from couchformation.resources.config_manager import ConfigurationManager

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
    ) -> None:
        version = variables.get("version") or variables.get("sw_version") or "latest"
        cluster_name = variables.get("cluster_name", project.name)
        data_path = variables.get("data_path", "/cbdata")
        services = group.services or variables.get("services", "data")

        commands = [f"bundlemgr -b CBS -V {version}"]
        if group.group == 0 and node.number == 1:
            commands.append(
                "swmgr cluster create "
                f"--name {cluster_name} "
                f"--password {password} "
                f"--ip-address {node.private_ip} "
                f"--external-ip-address {node.public_ip or node.private_ip} "
                f"--services {services} "
                f"--server-group {node.zone or 'default'} "
                f"--data-path {data_path}"
            )
        else:
            primary_ip = variables.get("primary_ip") or node.private_ip
            primary_ext = variables.get("primary_external_ip") or node.public_ip or node.private_ip
            commands.append(
                "swmgr cluster add "
                f"--name {cluster_name} "
                f"--password {password} "
                f"--ip-address {primary_ip} "
                f"--external-ip-address {primary_ext} "
                f"--services {services} "
                f"--server-group {node.zone or 'default'} "
                f"--data-path {data_path}"
            )

        self._execute(node, commands, group)

    def _execute(self, node: NodeResult, commands: list[str], group: NodeGroupConfig) -> None:
        cm = ConfigurationManager()
        ssh_key = group.ssh_key or cm.get("ssh.key")
        host = node.public_ip or node.private_ip
        if not host or not node.username or not ssh_key:
            logger.warning(f"Skipping couchbase finalizer for {node.node_name}: missing connection details")
            return
        for command in commands:
            logger.info(f"Finalizer couchbase: {command}")
            RunSSHCommand(ssh_key, node.username, host, command, "/tmp").exec()
