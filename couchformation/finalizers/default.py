from __future__ import annotations

import logging
from typing import Optional

from couchformation.constants import HOST_PREP_VERSION
from couchformation.finalizers.base import execute_node_command
from couchformation.models.cloud_ops import NodeResult
from couchformation.models.project import NodeGroupConfig, ProjectConfig

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
        primary_node: Optional[NodeResult] = None,
    ) -> None:
        host_prep_version = variables.get("host_prep_version", HOST_PREP_VERSION)
        is_windows = (getattr(group, "os_id", "") or "").lower() == "windows" or (getattr(node, "os_id", "") or "").lower() == "windows"

        if is_windows:
            commands = [
                'iex "& {$(irm https://raw.githubusercontent.com/couchbaselabs/host-prep-lib/main/bin/bootstrap.ps1)}"',
            ]
        else:
            commands = [
                (
                    "if command -v apt-get >/dev/null 2>&1; then "
                    "sudo DEBIAN_FRONTEND=noninteractive apt-get update -y && "
                    "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y curl git build-essential libssl-dev zlib1g-dev "
                    "libbz2-dev libreadline-dev libsqlite3-dev libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev "
                    "libffi-dev liblzma-dev libedit-dev; "
                    "elif command -v dnf >/dev/null 2>&1; then "
                    "sudo dnf install -y curl git gcc make patch zlib-devel bzip2 bzip2-devel readline-devel sqlite sqlite-devel "
                    "openssl-devel tk-devel libffi-devel xz-devel; "
                    "elif command -v yum >/dev/null 2>&1; then "
                    "sudo yum install -y curl git gcc make patch zlib-devel bzip2 bzip2-devel readline-devel sqlite sqlite-devel "
                    "openssl-devel tk-devel libffi-devel xz-devel; "
                    "fi"
                ),
                "[ -d \"$HOME/.asdf\" ] || git clone https://github.com/asdf-vm/asdf.git \"$HOME/.asdf\" --branch v0.15.0",
                (
                    '. "$HOME/.asdf/asdf.sh" && '
                    "(asdf plugin add python https://github.com/asdf-community/asdf-python.git || asdf plugin-add python || true) && "
                    "asdf install python 3.12.13 && "
                    "asdf global python 3.12.13"
                ),
                (
                    "grep -q '.asdf' ~/.bashrc 2>/dev/null || echo 'export PATH=\"$HOME/.asdf/bin:$HOME/.asdf/shims:$HOME/.local/bin:/usr/local/bin:$PATH\"' >> ~/.bashrc; "
                    "grep -q 'asdf.sh' ~/.bashrc 2>/dev/null || echo '[ -s \"$HOME/.asdf/asdf.sh\" ] && . \"$HOME/.asdf/asdf.sh\"' >> ~/.bashrc; "
                    "grep -q '.asdf' ~/.profile 2>/dev/null || echo 'export PATH=\"$HOME/.asdf/bin:$HOME/.asdf/shims:$HOME/.local/bin:/usr/local/bin:$PATH\"' >> ~/.profile; "
                    "grep -q 'asdf.sh' ~/.profile 2>/dev/null || echo '[ -s \"$HOME/.asdf/asdf.sh\" ] && . \"$HOME/.asdf/asdf.sh\"' >> ~/.profile; "
                    "true"
                ),
                "curl -LsSf https://astral.sh/uv/install.sh | sh",
                (
                    f'export PATH="$HOME/.local/bin:$PATH" && '
                    f"uv tool install https://github.com/mminichino/host-prep-lib/releases/download/{host_prep_version}/pyhostprep-{host_prep_version}-py3-none-any.whl"
                ),
                (
                    'export PATH="$HOME/.local/bin:$PATH" && '
                    "uv tool install ansible-core --with ansible"
                ),
                (
                    "sudo ln -sf $HOME/.local/bin/* /usr/local/bin/ 2>/dev/null || true; "
                    "sudo ln -sf $HOME/.asdf/shims/* /usr/local/bin/ 2>/dev/null || true; "
                    "sudo ln -sf $HOME/.asdf/bin/* /usr/local/bin/ 2>/dev/null || true"
                ),
            ]

        for command in commands:
            execute_node_command(node, group, command, password=password, check=True)
