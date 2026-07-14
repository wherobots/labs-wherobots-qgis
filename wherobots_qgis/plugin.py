import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon

from .core.connection import ConnectionManager


class WherobotsPlugin:
    """Main QGIS plugin class for Wherobots integration.

    Manages the plugin lifecycle: toolbar/menu setup, dock widget creation,
    and cleanup on unload.
    """

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.actions = []
        self.action = None
        self.menu = "&Wherobots"
        self.toolbar = None
        self.dock_widget = None

    def initGui(self):
        """Called by QGIS when the plugin is loaded. Sets up UI elements."""
        self.toolbar = self.iface.addToolBar("Wherobots")
        self.toolbar.setObjectName("WherobotsToolbar")

        icon_path = os.path.join(self.plugin_dir, "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.action = QAction(icon, "Wherobots", self.iface.mainWindow())
        self.action.setObjectName("WherobotsAction")
        self.action.setToolTip("Wherobots — open the Wherobots panel")
        self.action.setStatusTip(
            "Open the Wherobots panel for spatial SQL, upload, and raster operations"
        )
        # Checkable so the button reflects whether the dock is currently open.
        self.action.setCheckable(True)
        self.action.triggered.connect(self.run)

        self.toolbar.addAction(self.action)
        self.iface.addPluginToWebMenu(self.menu, self.action)
        self.actions.append(self.action)

    def unload(self):
        """Called by QGIS when the plugin is unloaded. Cleans up everything."""
        # Disconnect from Wherobots
        conn_mgr = ConnectionManager.instance()
        if conn_mgr.is_connected():
            conn_mgr.do_disconnect()

        # Remove UI elements
        for action in self.actions:
            self.iface.removePluginWebMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        self.actions.clear()

        if self.dock_widget:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.deleteLater()
            self.dock_widget = None

        if self.toolbar:
            del self.toolbar
            self.toolbar = None

    def run(self):
        """Toggle the Wherobots dock widget, keeping the toolbar button in sync."""
        if self.dock_widget is None:
            from .gui.dock_widget import DockWidget
            self.dock_widget = DockWidget(self.iface)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
            # Reflect dock visibility on the toolbar button, including when the
            # user closes the dock via its own close button.
            self.dock_widget.visibilityChanged.connect(self.action.setChecked)
            self.dock_widget.show()
        else:
            self.dock_widget.setVisible(not self.dock_widget.isVisible())
