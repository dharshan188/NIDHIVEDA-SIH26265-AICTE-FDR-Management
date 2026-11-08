"""Optional local services, or mandatory with --require-services / TL_REQUIRE_SERVICES=1.

An explicitly configured or reachable service must run its tests, never skip.
Credentials are supplied through environment variables; errors do not echo them.
"""
import os
import socket

import pytest
from sqlalchemy.engine import make_url


def endpoint_up(host, port):
    try:
        with socket.create_connection((host, int(port)), timeout=2):
            return True
    except OSError:
        return False


def config(name, required=False):
    variable, default, ports = {
        "clamav": ("TL_TEST_CLAMD", "127.0.0.1:3310", (3310,)),
        "s3": ("TL_TEST_S3", "127.0.0.1:8333", (8333,)),
        "mailpit": ("TL_TEST_SMTP", "127.0.0.1:1025:8025", (1025, 8025)),
        "postgres": ("TL_TEST_PG_URL", "127.0.0.1:55433", (55433,)),
    }[name]
    value = os.environ.get(variable)
    if name == "s3" and not value:
        endpoint = os.environ.get("TL_S3_ENDPOINT", default)
        default = endpoint
        ports = (endpoint.rsplit(":", 1)[-1],)
        access, secret = os.environ.get("TL_S3_ACCESS_KEY"), os.environ.get("TL_S3_SECRET_KEY")
        if access and secret:
            value = f"{endpoint},{access},{secret}"
    if not value and name in ("clamav", "mailpit"):
        host, *service_ports = default.split(":")
        if all(endpoint_up(host, port) for port in service_ports):
            value = default
    if not value:
        host = default.split(":")[0]
        reachable = any(endpoint_up(host, port) for port in ports)
        reason = f"ENVIRONMENT: {name} needs {variable}; " + ("local service reachable but credentials/configuration missing" if reachable else "local service unavailable")
        if required or reachable:
            pytest.fail(reason, pytrace=False)
        pytest.skip(reason + " (use --require-services to fail instead)")
    try:
        if name == "postgres":
            url = make_url(value)
            endpoints = [(url.host, url.port or 5432)]
        elif name == "s3":
            endpoint, access, secret = value.split(",")
            host, port = endpoint.split(":")
            assert access and secret
            endpoints = [(host, port)]
        else:
            host, *service_ports = value.split(":")
            endpoints = [(host, p) for p in service_ports]
        assert endpoints and all(endpoint_up(h, p) for h, p in endpoints)
    except (ValueError, AssertionError, TypeError):
        pytest.fail(f"ENVIRONMENT: {name}: invalid {variable} or required service endpoint unavailable", pytrace=False)
    return value
