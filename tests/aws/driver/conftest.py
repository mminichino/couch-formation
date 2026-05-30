from __future__ import annotations

from collections.abc import Callable

import pytest

from couchformation.network import NetworkDriver
from couchformation.resources.config_manager import ConfigurationManager
from couchformation.identity.id import UniqueId

UUID: UniqueId = UniqueId()


@pytest.fixture(autouse=True)
def _neutralize_fatal_error(monkeypatch):
    import couchformation.exception as exc_mod

    def _init(self, message):
        Exception.__init__(self, message)
        self.message = message

    monkeypatch.setattr(exc_mod.FatalError, "__init__", _init)
    yield


@pytest.fixture(scope="module")
def aws_parameters():
    cm = ConfigurationManager()
    params = {
        "cloud": "aws",
        "region": "us-east-2",
        "project": "pytest-aws-unittest",
    }
    if cm.get("aws.tags"):
        params["tags"] = cm.get("aws.tags")
    if cm.get("ssh.key"):
        params["ssh_key"] = cm.get("ssh.key")
    return params


@pytest.fixture
def cleanup(request):
    handlers: list[Callable[[], None]] = []

    def register(fn: Callable[[], None]) -> None:
        handlers.append(fn)

    def _run_cleanup() -> None:
        for fn in reversed(handlers):
            try:
                fn()
            except Exception:
                pass

    request.addfinalizer(_run_cleanup)
    return register


@pytest.fixture
def cidr_util(aws_parameters):
    util = NetworkDriver()
    from couchformation.aws.driver.network import Network

    for net in Network(aws_parameters).cidr_list:
        util.add_network(net)
    return util


def unique_name(prefix: str) -> str:
    return f"{prefix}-{UUID.short}"


def domain_name() -> str:
    cm = ConfigurationManager()
    if cm.get("aws.domain"):
        return f"{UUID.min}.{cm.get('aws.domain')}"
    else:
        return f"{UUID.min}.example.com"
