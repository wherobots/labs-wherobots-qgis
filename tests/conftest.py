"""Pytest configuration: install QGIS stubs before any plugin import."""

import pytest

from tests.support import (
    dbapi_installed,
    install_qgis_stubs,
    load_connection,
    reset_qgs_settings,
)

install_qgis_stubs()


@pytest.fixture(autouse=True)
def _isolate_settings():
    """Each test starts with an empty QgsSettings store."""
    reset_qgs_settings()
    yield


@pytest.fixture
def connection_missing():
    """core.connection imported as if the dependency were not installed."""
    return load_connection(available=False)


@pytest.fixture
def connection_present():
    """core.connection imported with the real dependency; skip if absent."""
    if not dbapi_installed():
        pytest.skip("wherobots-python-dbapi not installed in this environment")
    return load_connection(available=True)
