"""Stable collection-only IDs: do not put generated PDF bytes into parameter names."""
def pytest_make_parametrize_id(config, val, argname):
    if isinstance(val, bytes):
        return argname
    return None
