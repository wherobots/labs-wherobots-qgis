"""Pytest configuration: install QGIS stubs before any plugin import."""

import pytest

from tests.support import dbapi_installed, install_qgis_stubs, load_connection

install_qgis_stubs()


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
