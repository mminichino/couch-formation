from __future__ import annotations

import logging

from couchformation.constants import HOST_PREP_VERSION
from couchformation.models.cloud_ops import NodeResult
from couchformation.models.project import NodeGroupConfig, ProjectConfig
from couchformation.provisioner.ssh import RunSSHCommand
from couchformation.resources.config_manager import ConfigurationManager

logger = logging.getLogger("couchformation.finalizers.default")
logger.addHandler(logging.NullHandler())


class DefaultFinalizer:
    name = "default"

    def run(
        self,
        project: ProjectConfig,
        group: NodeGroupConfig,
        node: NodeResult,
        password: str,
        variables: dict[str, str],
    ) -> None:
        host_prep_version = variables.get("host_prep_version", HOST_PREP_VERSION)
        commands = [
            "curl -fsSL https://asdf-vm.com/install.sh | bash",
            "asdf install python 3.12.13",
            "asdf set -u python 3.12.13",
            "curl -LsSf https://astral.sh/uv/install.sh | sh",
            f"uv tool install https://github.com/mminichino/host-prep-lib/releases/download/{host_prep_version}/pyhostprep-{host_prep_version}-py3-none-any.whl",
            "uv tool install ansible-core --with ansible",
        ]
        self._execute(node, commands, group)

    def _execute(self, node: NodeResult, commands: list[str], group: NodeGroupConfig) -> None:
        cm = ConfigurationManager()
        ssh_key = group.ssh_key or cm.get("ssh.key")
        host = node.public_ip or node.private_ip
        if not host or not node.username or not ssh_key:
            logger.warning(f"Skipping default finalizer for {node.node_name}: missing connection details")
            return
        for command in commands:
            logger.info(f"Finalizer default: {command}")
            RunSSHCommand(ssh_key, node.username, host, command, "/tmp").exec()
