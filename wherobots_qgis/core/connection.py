from qgis.PyQt.QtCore import QObject, pyqtSignal

from wherobots.db import connect as wb_connect
from wherobots.db.region import Region
from wherobots.db.runtime import Runtime


# Dynamically build maps from whatever the installed library actually provides
REGION_MAP = {r.value: r for r in Region}
RUNTIME_MAP = {r.name: r for r in Runtime}

REGION_LABELS = list(REGION_MAP.keys())
RUNTIME_LABELS = list(RUNTIME_MAP.keys())


class ConnectionManager(QObject):
    """Manages a single Wherobots DB-API connection.

    Emits Qt signals for connection state changes so the GUI can react.
    The connection is created on-demand and kept alive until explicitly
    disconnected or the plugin is unloaded.
    """

    connected = pyqtSignal()
    disconnected = pyqtSignal()
    connection_error = pyqtSignal(str)

    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self._conn = None
        self._cursor = None

    def is_connected(self):
        return self._conn is not None

    def do_connect(self, api_key, region_key="aws-us-west-2", runtime_key="TINY"):
        """Establish connection to Wherobots. Call from a background thread.

        :param api_key: Wherobots API key string
        :param region_key: key into REGION_MAP
        :param runtime_key: key into RUNTIME_MAP
        :raises Exception: on connection failure
        """
        region = REGION_MAP.get(region_key, Region.AWS_US_WEST_2)
        runtime = RUNTIME_MAP.get(runtime_key, Runtime.TINY)

        self._conn = wb_connect(
            host="api.cloud.wherobots.com",
            api_key=api_key,
            runtime=runtime,
            region=region,
        )
        self._cursor = self._conn.cursor()

    def do_disconnect(self):
        """Close the connection. Safe to call even if not connected."""
        if self._cursor:
            try:
                self._cursor.close()
            except Exception:
                pass
            self._cursor = None
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def get_cursor(self):
        """Return the active cursor or raise if not connected."""
        if self._cursor is None:
            raise RuntimeError("Not connected to Wherobots")
        return self._cursor

    def get_connection(self):
        """Return the active connection or raise if not connected."""
        if self._conn is None:
            raise RuntimeError("Not connected to Wherobots")
        return self._conn
