from __future__ import annotations

import logging
from typing import Optional

from couchformation.models.cloud_ops import NodeResult
from couchformation.models.project import NodeGroupConfig
from couchformation.provisioner.ssh import RunSSHCommand
from couchformation.provisioner.winrm import WinRMProvisioner
from couchformation.resources.config_manager import ConfigurationManager

logger = logging.getLogger("couchformation.finalizers")


def execute_node_command(
    node: NodeResult,
    group: NodeGroupConfig,
    command: str,
    password: Optional[str] = None,
    check: bool = True,
) -> int:
    host = node.public_ip or node.private_ip
    if not host or not node.username:
        logger.warning(f"Skipping command for {node.node_name or node.name}: missing connection details")
        return 0

    is_windows = (getattr(group, "os_id", "") or "").lower() == "windows" or (getattr(node, "os_id", "") or "").lower() == "windows"

    if is_windows:
        params = {
            "public_ip": host,
            "private_ip": node.private_ip or host,
            "username": node.username,
            "host_password": password or group.password or "password",
        }
        logger.info(f"Finalizer WinRM on {host}: {command}")
        code = WinRMProvisioner(params, command=command, root=True).run()
        if check and code != 0:
            raise RuntimeError(f"WinRM command '{command}' failed on {host} with status code {code}")
        return code

    cm = ConfigurationManager()
    ssh_key = group.ssh_key or cm.get("ssh.key")
    if not ssh_key:
        raise RuntimeError(f"SSH key not found for node {node.node_name or node.name}")

    env_wrapper = (
        'export PATH="$HOME/.asdf/bin:$HOME/.asdf/shims:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"; '
        '[ -s "$HOME/.asdf/asdf.sh" ] && . "$HOME/.asdf/asdf.sh"; '
    )
    full_command = f"{env_wrapper} {command}"
    logger.info(f"Finalizer SSH on {host}: {command}")
    exit_code, stdout, stderr = RunSSHCommand(ssh_key, node.username, host, full_command, "/tmp").exec()

    out_text = stdout.read() if hasattr(stdout, "read") else ""
    err_text = stderr.read() if hasattr(stderr, "read") else ""

    if out_text:
        for line in out_text.strip().splitlines():
            logger.info(f"{host}: {line}")
    if err_text:
        for line in err_text.strip().splitlines():
            logger.debug(f"{host} [stderr]: {line}")

    if check and exit_code != 0:
        logger.error(f"Command '{command}' failed on {host} (exit code {exit_code}):\n{err_text}\n{out_text}")
        raise RuntimeError(f"Command '{command}' failed on {host} with exit code {exit_code}: {err_text or out_text}")

    return exit_code
