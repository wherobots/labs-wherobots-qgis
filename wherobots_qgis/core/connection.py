from qgis.PyQt.QtCore import QObject, pyqtSignal

# The wherobots-python-dbapi package is an external dependency that must be
# installed into QGIS's bundled Python. Import it lazily-at-module-load but
# guarded, so a missing dependency degrades to an actionable error message
# instead of crashing plugin load with a cryptic ImportError.
try:
    from wherobots.db import connect as wb_connect
    from wherobots.db.region import Region
    from wherobots.db.runtime import Runtime

    DBAPI_AVAILABLE = True
except ImportError:
    wb_connect = None
    Region = None
    Runtime = None

    DBAPI_AVAILABLE = False


# Correct, path-independent install guidance. The QGIS Python on macOS is not
# at a fixed path (the command in older docs, .../QGIS.app/Contents/MacOS/bin/
# python3, does not exist on many installs), so we point users at sys.executable
# from the QGIS Python Console, which always resolves to the running interpreter.
INSTALL_INSTRUCTIONS = (
    "The 'wherobots-python-dbapi' package is required but is not installed in "
    "QGIS's Python environment.\n\n"
    "Install it from the QGIS Python Console (Plugins → Python Console):\n"
    "    import subprocess, sys\n"
    "    subprocess.check_call([sys.executable, '-m', 'pip', 'install', "
    "'wherobots-python-dbapi'])\n\n"
    "Then restart QGIS. Using sys.executable avoids hardcoded interpreter paths, "
    "which differ across platforms and QGIS installations."
)


# Dynamically build maps from whatever the installed library actually provides.
# Empty when the dependency is missing so the GUI still loads.
REGION_MAP = {r.value: r for r in Region} if DBAPI_AVAILABLE else {}
RUNTIME_MAP = {r.name: r for r in Runtime} if DBAPI_AVAILABLE else {}

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
        if not DBAPI_AVAILABLE:
            raise RuntimeError(INSTALL_INSTRUCTIONS)

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
