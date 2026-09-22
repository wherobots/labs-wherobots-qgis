"""Tests for core.connection — covers the CUS-36 fix.

CUS-36: a missing/mis-installed wherobots-python-dbapi crashed plugin load
with a cryptic ImportError, and the documented install command pointed at a
macOS path that does not exist. The plugin must instead load gracefully and
hand the user a correct, path-independent install instruction.
"""

import pytest


# --- Dependency-missing path (the failure mode from the bug report) ---------

def test_module_imports_when_dependency_missing(connection_missing):
    """Plugin must still load; a missing dep should not raise at import."""
    assert connection_missing.DBAPI_AVAILABLE is False


def test_labels_empty_when_dependency_missing(connection_missing):
    """GUI combos read these at construction — they must exist and be empty."""
    assert connection_missing.REGION_MAP == {}
    assert connection_missing.RUNTIME_MAP == {}
    assert connection_missing.REGION_LABELS == []
    assert connection_missing.RUNTIME_LABELS == []


def test_do_connect_raises_actionable_error_when_missing(connection_missing):
    mgr = connection_missing.ConnectionManager()
    with pytest.raises(RuntimeError) as exc:
        mgr.do_connect("fake-api-key")
    message = str(exc.value)
    assert "wherobots-python-dbapi" in message
    assert "sys.executable" in message
    assert "Python Console" in message


def test_install_instructions_avoid_the_broken_macos_path(connection_missing):
    """Regression guard for the exact path from the bug report."""
    broken = "/Applications/QGIS.app/Contents/MacOS/bin/python3"
    assert broken not in connection_missing.INSTALL_INSTRUCTIONS


# --- Dependency-present path (normal operation still works) ------------------

def test_maps_populated_when_dependency_present(connection_present):
    assert connection_present.DBAPI_AVAILABLE is True
    assert connection_present.REGION_LABELS, "expected at least one region"
    assert connection_present.RUNTIME_LABELS, "expected at least one runtime"
    assert "aws-us-west-2" in connection_present.REGION_LABELS


# --- ConnectionManager state, independent of the dependency ------------------

def test_instance_is_singleton(connection_missing):
    a = connection_missing.ConnectionManager.instance()
    b = connection_missing.ConnectionManager.instance()
    assert a is b


def test_get_cursor_raises_when_not_connected(connection_missing):
    mgr = connection_missing.ConnectionManager()
    with pytest.raises(RuntimeError, match="Not connected"):
        mgr.get_cursor()


def test_get_connection_raises_when_not_connected(connection_missing):
    mgr = connection_missing.ConnectionManager()
    with pytest.raises(RuntimeError, match="Not connected"):
        mgr.get_connection()


def test_disconnect_is_safe_when_not_connected(connection_missing):
    mgr = connection_missing.ConnectionManager()
    mgr.do_disconnect()  # must not raise
    assert mgr.is_connected() is False


def test_disconnect_logs_close_failures_instead_of_swallowing(connection_missing):
    """A failing close() must still disconnect, but leave a trace in the log."""
    from tests.support import clear_logged_messages, logged_messages

    class Failing:
        def close(self):
            raise RuntimeError("socket already gone")

    clear_logged_messages()
    mgr = connection_missing.ConnectionManager()
    mgr._cursor = Failing()
    mgr._conn = Failing()

    mgr.do_disconnect()  # must not raise

    assert mgr.is_connected() is False
    assert mgr._cursor is None
    messages = [m[0] for m in logged_messages()]
    assert any("cursor" in m and "socket already gone" in m for m in messages)
    assert any("connection" in m and "socket already gone" in m for m in messages)
