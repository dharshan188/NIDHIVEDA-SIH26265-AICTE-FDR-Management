"""Deterministic tests of optional/required/auto-detected service gates; no service mutations."""
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend/tests"))
import service_config

checks = 0
settings = {
    "clamav": ("TL_TEST_CLAMD", "127.0.0.1:3310"),
    "s3": ("TL_TEST_S3", "127.0.0.1:8333,fixture-access,fixture-secret"),
    "mailpit": ("TL_TEST_SMTP", "127.0.0.1:1025:8025"),
    "postgres": ("TL_TEST_PG_URL", "postgresql+psycopg://fixture@127.0.0.1:55433/fixture"),
}
for name, (variable, value) in settings.items():
    with patch.dict(service_config.os.environ, {}, clear=True), patch.object(service_config, "endpoint_up", return_value=False):
        with pytest.raises(pytest.skip.Exception, match="ENVIRONMENT"):
            service_config.config(name)
        checks += 1
        with pytest.raises(pytest.fail.Exception, match="ENVIRONMENT"):
            service_config.config(name, required=True)
        checks += 1
    with patch.dict(service_config.os.environ, {variable: value}, clear=True):
        with patch.object(service_config, "endpoint_up", return_value=False):
            with pytest.raises(pytest.fail.Exception, match="endpoint unavailable"):
                service_config.config(name)
            checks += 1
        with patch.object(service_config, "endpoint_up", return_value=True):
            assert service_config.config(name, required=True) == value
            checks += 1
    print(f"{name}: optional missing = explicit ENVIRONMENT skip; required missing = FAIL; configured missing = FAIL; configured available = run")
with patch.dict(service_config.os.environ, {}, clear=True), patch.object(service_config, "endpoint_up", return_value=True):
    for name in ("clamav", "mailpit"):
        assert service_config.config(name) == settings[name][1]
        checks += 1
    for name in ("s3", "postgres"):
        with pytest.raises(pytest.fail.Exception, match="reachable but credentials/configuration missing"):
            service_config.config(name)
        checks += 1
with patch.dict(service_config.os.environ, {"TL_S3_ENDPOINT": "127.0.0.1:8334"}, clear=True), patch.object(service_config, "endpoint_up", return_value=True):
    with pytest.raises(pytest.fail.Exception, match="reachable but credentials/configuration missing"):
        service_config.config("s3")
    checks += 1
print(f"{checks} service-gating checks passed; reachable services cannot silently skip.")
