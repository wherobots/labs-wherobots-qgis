"""Tests for core.query_task background tasks (QgsTask subclasses)."""

import importlib

import pytest

from tests.support import FakeSignal, install_qgis_stubs

install_qgis_stubs()
query_task = importlib.import_module("wherobots_qgis.core.query_task")


class FakeCursor:
    def __init__(self, columns=(), rows=None, raise_on_execute=None):
        self.description = [(c,) for c in columns]
        self._rows = rows
        self._raise = raise_on_execute
        self.executed = None

    def execute(self, sql):
        self.executed = sql
        if self._raise:
            raise self._raise

    def fetchall(self):
        return self._rows


class FakeConnMgr:
    def __init__(self, cursor=None, connect_error=None):
        self._cursor = cursor
        self._connect_error = connect_error
        self.connected = FakeSignal()
        self.connection_error = FakeSignal()
        self.connect_calls = []

    def get_cursor(self):
        return self._cursor

    def do_connect(self, api_key, region, runtime):
        self.connect_calls.append((api_key, region, runtime))
        if self._connect_error:
            raise self._connect_error


# --- QueryTask --------------------------------------------------------------

def test_query_task_run_success_captures_columns():
    cursor = FakeCursor(columns=["id", "geometry"], rows="<df>")
    task = query_task.QueryTask("SELECT 1", FakeConnMgr(cursor=cursor))
    assert task.run() is True
    assert task.columns == ["id", "geometry"]
    assert task.result_df == "<df>"
    assert task.error_message is None


def test_query_task_run_captures_error():
    cursor = FakeCursor(raise_on_execute=ValueError("bad sql"))
    task = query_task.QueryTask("SELECT boom", FakeConnMgr(cursor=cursor))
    assert task.run() is False
    assert "bad sql" in task.error_message


# --- ConnectTask ------------------------------------------------------------

def test_connect_task_success_emits_connected():
    mgr = FakeConnMgr()
    task = query_task.ConnectTask(mgr, "key", "aws-us-west-2", "TINY")
    assert task.run() is True
    assert mgr.connect_calls == [("key", "aws-us-west-2", "TINY")]
    task.finished(True)
    assert len(mgr.connected.emissions) == 1
    assert mgr.connection_error.emissions == []


def test_connect_task_failure_emits_error_message():
    mgr = FakeConnMgr(connect_error=RuntimeError("install wherobots-python-dbapi"))
    task = query_task.ConnectTask(mgr, "key", "aws-us-west-2", "TINY")
    assert task.run() is False
    assert "install wherobots-python-dbapi" in task.error_message
    task.finished(False)
    assert mgr.connected.emissions == []
    assert mgr.connection_error.emissions == [("install wherobots-python-dbapi",)]


def test_connect_task_failure_defaults_message_when_none():
    mgr = FakeConnMgr()
    task = query_task.ConnectTask(mgr, "key", "aws-us-west-2", "TINY")
    # Simulate finished() being called on failure without a captured message.
    task.finished(False)
    assert mgr.connection_error.emissions == [("Unknown error",)]
