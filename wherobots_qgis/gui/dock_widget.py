from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QTabWidget,
)
from qgis.PyQt.QtCore import Qt

from ..core.connection import ConnectionManager
from .connection_widget import ConnectionWidget
from .query_tab import QueryTab
from .upload_tab import UploadTab
from .raster_tab import RasterTab


class DockWidget(QDockWidget):
    """Main dock widget for the Wherobots plugin.

    Contains a connection widget at the top (always visible) and a
    tabbed interface below with Query, Upload, and Raster tabs.
    Tabs are disabled until a connection is established.
    """

    def __init__(self, iface, parent=None):
        super().__init__("Wherobots", parent)
        self.iface = iface
        self.setObjectName("WherobotsDockWidget")
        self.conn_mgr = ConnectionManager.instance()
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)

        # Connection controls (always visible)
        self.connection_widget = ConnectionWidget()
        layout.addWidget(self.connection_widget)

        # Tabbed interface
        self.tab_widget = QTabWidget()
        self.query_tab = QueryTab(self.iface)
        self.upload_tab = UploadTab(self.iface)
        self.raster_tab = RasterTab(self.iface)

        self.tab_widget.addTab(self.query_tab, "SQL Query")
        self.tab_widget.addTab(self.upload_tab, "Upload")
        self.tab_widget.addTab(self.raster_tab, "Raster")

        # Disable tabs until connected
        self.tab_widget.setEnabled(False)
        layout.addWidget(self.tab_widget)

        container.setLayout(layout)
        self.setWidget(container)

    def _connect_signals(self):
        self.conn_mgr.connected.connect(self._on_connected)
        self.conn_mgr.disconnected.connect(self._on_disconnected)

    def _on_connected(self):
        self.tab_widget.setEnabled(True)

    def _on_disconnected(self):
        self.tab_widget.setEnabled(False)
        # Cancel all running tasks across all tabs
        self.query_tab.cancel_running_task()
        self.upload_tab.cancel_running_task()
        self.raster_tab.cancel_running_task()
