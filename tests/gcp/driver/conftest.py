from __future__ import annotations

import uuid
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
def gcp_parameters():
    cm = ConfigurationManager()
    params = {
        "cloud": "gcp",
        "region": "us-central1",
        "project": "pytest-gcp-unittest",
    }
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
def cidr_util(gcp_parameters):
    util = NetworkDriver()
    from couchformation.gcp.driver.network import Network

    for net in Network(gcp_parameters).cidr_list:
        util.add_network(net)
    return util


def unique_name(prefix: str) -> str:
    return f"{prefix}-{UUID.short}"


def domain_name() -> str:
    cm = ConfigurationManager()
    if cm.get("gcp.domain"):
        return f"{UUID.min}.{cm.get('gcp.domain')}"
    else:
        return f"{UUID.min}.example.com"
