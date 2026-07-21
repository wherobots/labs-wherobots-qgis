from qgis.core import QgsTask

from ..utils.qt_compat import TASK_CAN_CANCEL


# Max rows the Wherobots DB-API will return directly
DIRECT_ROW_LIMIT = 1000


class QueryTask(QgsTask):
    """Background task that executes a SQL query against Wherobots.

    Results are fetched directly via cursor.fetchall(). The query should
    include a LIMIT clause — the DB-API enforces a hard cap of 1000 rows.
    """

    def __init__(self, sql, connection_manager, max_rows=100, description="Running query"):
        super().__init__(description, TASK_CAN_CANCEL)
        self.sql = sql
        self.conn_mgr = connection_manager
        self.max_rows = max_rows

        # Results populated by run()
        self.columns = None
        self.result_df = None  # Pandas DataFrame from fetchall()
        self.error_message = None

    def run(self):
        """Execute in background thread. Results stored as a Pandas DataFrame."""
        try:
            cursor = self.conn_mgr.get_cursor()
            cursor.execute(self.sql)
            self.columns = [desc[0] for desc in cursor.description] if cursor.description else []
            self.result_df = cursor.fetchall()  # returns a Pandas DataFrame
            return True
        except Exception as e:
            self.error_message = str(e)
            return False

    def finished(self, result):
        """Called on main thread when task completes."""
        pass


class ConnectTask(QgsTask):
    """Background task to establish a Wherobots connection without blocking the UI."""

    def __init__(self, connection_manager, api_key, region, runtime):
        super().__init__("Connecting to Wherobots", TASK_CAN_CANCEL)
        self.conn_mgr = connection_manager
        self.api_key = api_key
        self.region = region
        self.runtime = runtime
        self.error_message = None

    def run(self):
        try:
            self.conn_mgr.do_connect(self.api_key, self.region, self.runtime)
            return True
        except Exception as e:
            self.error_message = str(e)
            return False

    def finished(self, result):
        if result:
            self.conn_mgr.connected.emit()
        else:
            self.conn_mgr.connection_error.emit(self.error_message or "Unknown error")


class BrowseTablesTask(QgsTask):
    """Background task to list schemas or tables."""

    def __init__(self, connection_manager, sql, description="Browsing catalog"):
        super().__init__(description, TASK_CAN_CANCEL)
        self.conn_mgr = connection_manager
        self.sql = sql
        self.results = []
        self.error_message = None

    def run(self):
        try:
            cursor = self.conn_mgr.get_cursor()
            cursor.execute(self.sql)
            df = cursor.fetchall()  # Pandas DataFrame
            self.results = df.values.tolist() if not df.empty else []
            return True
        except Exception as e:
            self.error_message = str(e)
            return False

    def finished(self, result):
        pass
