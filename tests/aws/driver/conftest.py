"""Common fixtures for couchformation.aws.driver unit tests.

Provides:
- A neutralized ``FatalError`` so ``AWSDriverError`` instances can be raised
  and inspected without triggering ``sys.exit`` or crash-log side effects.
- Mocked ``boto3.Session`` / ``boto3.client`` so driver classes can be
  instantiated and exercised without any real AWS credentials or calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _neutralize_fatal_error(monkeypatch):
    """Replace ``FatalError.__init__`` so AWSDriverError behaves like a plain
    exception (no log writes, no ``sys.exit``).
    """
    import couchformation.exception as exc_mod

    def _init(self, message):
        Exception.__init__(self, message)
        self.message = message

    monkeypatch.setattr(exc_mod.FatalError, "__init__", _init)
    yield


class _ClientRegistry:
    """Holds mocked boto3 clients keyed by service name."""

    def __init__(self):
        self.clients: dict[str, MagicMock] = {}

    def get(self, name: str) -> MagicMock:
        if name not in self.clients:
            self.clients[name] = MagicMock(name=f"{name}_client")
        return self.clients[name]


@pytest.fixture
def aws_clients(monkeypatch):
    """Mock boto3 session/client construction for the AWS driver modules.

    Returns a ``_ClientRegistry`` whose ``get(name)`` yields the same mock
    ``CloudBase`` will receive for that service.  Tests configure the mock
    via ``aws_clients.get('ec2').<method>.return_value = ...`` before
    instantiating the driver class.
    """
    registry = _ClientRegistry()

    session = MagicMock(name="boto3_session")
    session.region_name = "us-east-1"

    def _session_client(name, *args, **kwargs):
        return registry.get(name)

    session.client.side_effect = _session_client

    import couchformation.aws.driver.base as base_mod

    monkeypatch.setattr(base_mod.boto3, "Session", lambda *a, **kw: session)
    monkeypatch.setattr(base_mod.boto3, "client", _session_client)

    registry.session = session
    return registry


@pytest.fixture
def cloud_base(aws_clients):
    """Return an initialized ``CloudBase`` with mocked clients."""
    from couchformation.aws.driver.base import CloudBase

    return CloudBase({})


def make_client_error(code: str, operation: str = "DescribeStuff"):
    """Build a ``botocore.exceptions.ClientError`` matching ``code``."""
    from botocore.exceptions import ClientError

    return ClientError(
        {"Error": {"Code": code, "Message": code}}, operation
    )
