from qgis.core import QgsTask

from ..utils.layer_utils import layer_to_insert_sql
from ..utils.qt_compat import TASK_CAN_CANCEL


class UploadTask(QgsTask):
    """Background task that uploads a QGIS vector layer to a Wherobots table.

    Reads features from the layer, generates CREATE TABLE and batched INSERT
    statements, and executes them sequentially via the DB-API cursor.
    """

    def __init__(self, layer, table_name, connection_manager):
        super().__init__(f"Uploading to {table_name}", TASK_CAN_CANCEL)
        self.layer = layer
        self.table_name = table_name
        self.conn_mgr = connection_manager
        self.error_message = None
        self.statements_executed = 0

    def run(self):
        try:
            cursor = self.conn_mgr.get_cursor()

            for sql in layer_to_insert_sql(self.layer, self.table_name):
                if self.isCanceled():
                    return False
                cursor.execute(sql)
                self.statements_executed += 1
                self.setProgress(
                    min(self.statements_executed * 10, 99)
                )

            return True
        except Exception as e:
            self.error_message = str(e)
            return False

    def finished(self, result):
        pass
