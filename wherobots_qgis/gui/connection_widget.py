from qgis.PyQt.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QLabel,
    QCheckBox,
    QGroupBox,
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsApplication

from ..core.connection import ConnectionManager, REGION_LABELS, RUNTIME_LABELS
from ..core.query_task import ConnectTask
from ..utils.settings import PluginSettings


class ConnectionWidget(QWidget):
    """Widget for configuring and managing the Wherobots connection.

    Always visible at the top of the dock widget. Provides API key input,
    region/runtime selection, and connect/disconnect controls.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = PluginSettings()
        self.conn_mgr = ConnectionManager.instance()
        self._connect_task = None
        self._setup_ui()
        self._load_settings()
        self._connect_signals()

    def _setup_ui(self):
        group = QGroupBox("Connection")
        group_layout = QVBoxLayout()

        # API key row
        key_layout = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Enter Wherobots API key")
        key_layout.addWidget(QLabel("API Key:"))
        key_layout.addWidget(self.api_key_input)
        group_layout.addLayout(key_layout)

        # Region and runtime row
        options_layout = QHBoxLayout()
        self.region_combo = QComboBox()
        self.region_combo.addItems(REGION_LABELS)
        options_layout.addWidget(QLabel("Region:"))
        options_layout.addWidget(self.region_combo)

        self.runtime_combo = QComboBox()
        self.runtime_combo.addItems(RUNTIME_LABELS)
        options_layout.addWidget(QLabel("Runtime:"))
        options_layout.addWidget(self.runtime_combo)
        group_layout.addLayout(options_layout)

        # Save credentials + buttons row
        controls_layout = QHBoxLayout()
        self.save_creds_checkbox = QCheckBox("Save credentials")
        controls_layout.addWidget(self.save_creds_checkbox)
        controls_layout.addStretch()

        self.connect_btn = QPushButton("Connect")
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setEnabled(False)
        controls_layout.addWidget(self.connect_btn)
        controls_layout.addWidget(self.disconnect_btn)
        group_layout.addLayout(controls_layout)

        # Status label
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: gray; font-style: italic;")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        group_layout.addWidget(self.status_label)

        group.setLayout(group_layout)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(group)
        self.setLayout(main_layout)

    def _load_settings(self):
        if self.settings.get_save_credentials():
            self.save_creds_checkbox.setChecked(True)
            self.api_key_input.setText(self.settings.get_api_key())

        region = self.settings.get_region()
        idx = self.region_combo.findText(region)
        if idx >= 0:
            self.region_combo.setCurrentIndex(idx)

        runtime = self.settings.get_runtime()
        idx = self.runtime_combo.findText(runtime)
        if idx >= 0:
            self.runtime_combo.setCurrentIndex(idx)

    def _connect_signals(self):
        self.connect_btn.clicked.connect(self._on_connect)
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        self.conn_mgr.connected.connect(self._on_connected)
        self.conn_mgr.disconnected.connect(self._on_disconnected)
        self.conn_mgr.connection_error.connect(self._on_connection_error)

    def _on_connect(self):
        api_key = self.api_key_input.text().strip()
        if not api_key:
            self.status_label.setText("Please enter an API key")
            self.status_label.setStyleSheet("color: red;")
            return

        # Save settings
        if self.save_creds_checkbox.isChecked():
            self.settings.set_api_key(api_key)
            self.settings.set_save_credentials(True)
        else:
            self.settings.clear_api_key()
            self.settings.set_save_credentials(False)

        self.settings.set_region(self.region_combo.currentText())
        self.settings.set_runtime(self.runtime_combo.currentText())

        # Update UI
        self.status_label.setText("Connecting... (runtime may take a minute to start)")
        self.status_label.setStyleSheet("color: orange;")
        self.connect_btn.setEnabled(False)
        self._set_inputs_enabled(False)

        # Launch connect task
        self._connect_task = ConnectTask(
            self.conn_mgr,
            api_key,
            self.region_combo.currentText(),
            self.runtime_combo.currentText(),
        )
        QgsApplication.taskManager().addTask(self._connect_task)

    def _on_disconnect(self):
        self.conn_mgr.do_disconnect()
        self.conn_mgr.disconnected.emit()

    def _on_connected(self):
        self.status_label.setText("Connected")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)

    def _on_disconnected(self):
        self.status_label.setText("Disconnected")
        self.status_label.setStyleSheet("color: gray; font-style: italic;")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self._set_inputs_enabled(True)

    def _on_connection_error(self, message):
        self.status_label.setText(f"Error: {message}")
        self.status_label.setStyleSheet("color: red;")
        self.connect_btn.setEnabled(True)
        self._set_inputs_enabled(True)

    def _set_inputs_enabled(self, enabled):
        self.api_key_input.setEnabled(enabled)
        self.region_combo.setEnabled(enabled)
        self.runtime_combo.setEnabled(enabled)
        self.save_creds_checkbox.setEnabled(enabled)
