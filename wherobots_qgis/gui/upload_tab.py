from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QLineEdit,
    QGroupBox,
    QProgressBar,
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsApplication, QgsMapLayerProxyModel

from qgis.gui import QgsMapLayerComboBox

from ..core.connection import ConnectionManager
from ..core.upload_task import UploadTask
from ..utils.sql import quote_qualified_name


class UploadTab(QWidget):
    """Tab for uploading a QGIS vector layer to a Wherobots table.

    Provides a layer selector (filtered to vector layers), a target table
    name input, and an upload button that runs in the background.
    """

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.conn_mgr = ConnectionManager.instance()
        self._upload_task = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)

        # --- Source layer ---
        source_group = QGroupBox("Source Layer")
        source_layout = QVBoxLayout()

        source_layout.addWidget(QLabel("Select a layer from your map:"))
        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        source_layout.addWidget(self.layer_combo)

        # Show feature count for selected layer
        self.layer_info_label = QLabel("")
        self.layer_info_label.setStyleSheet("color: gray; font-size: 11px;")
        source_layout.addWidget(self.layer_info_label)

        source_group.setLayout(source_layout)
        layout.addWidget(source_group)

        # --- Target table ---
        target_group = QGroupBox("Destination Table")
        target_layout = QVBoxLayout()

        target_layout.addWidget(QLabel("Fully qualified table name:"))
        self.table_name_input = QLineEdit()
        self.table_name_input.setPlaceholderText(
            "e.g., org_catalog.my_database.my_table"
        )
        target_layout.addWidget(self.table_name_input)

        hint = QLabel("Format: catalog.database.table_name")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        target_layout.addWidget(hint)

        target_group.setLayout(target_layout)
        layout.addWidget(target_group)

        # --- Upload / Cancel buttons ---
        btn_layout = QHBoxLayout()
        self.upload_btn = QPushButton("Upload Layer to Wherobots")
        self.upload_btn.setMinimumHeight(36)
        self.upload_btn.setStyleSheet(
            "QPushButton { background-color: #16a34a; color: white; font-weight: bold; }"
            "QPushButton:disabled { background-color: #86efac; }"
        )
        btn_layout.addWidget(self.upload_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumHeight(36)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setStyleSheet(
            "QPushButton { background-color: #dc2626; color: white; font-weight: bold; }"
        )
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        # --- Progress ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        # --- Status ---
        self.status_label = QTextEdit()
        self.status_label.setReadOnly(True)
        self.status_label.setMaximumHeight(80)
        self.status_label.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(self.status_label)

        layout.addStretch()
        self.setLayout(layout)

        # --- Signals ---
        self.layer_combo.layerChanged.connect(self._on_layer_changed)
        self.upload_btn.clicked.connect(self._on_upload)
        self.cancel_btn.clicked.connect(self._on_cancel)
        self._on_layer_changed(self.layer_combo.currentLayer())

    def _on_layer_changed(self, layer):
        if layer:
            count = layer.featureCount()
            geom_type = layer.geometryType().name if hasattr(layer.geometryType(), 'name') else str(layer.geometryType())
            self.layer_info_label.setText(
                f"{count} features | {geom_type}"
            )
        else:
            self.layer_info_label.setText("")

    def _on_upload(self):
        layer = self.layer_combo.currentLayer()
        if not layer:
            self.status_label.setText("Please select a layer.")
            self.status_label.setStyleSheet("color: red; background-color: transparent; border: none;")
            return

        table_name = self.table_name_input.text().strip()
        if not table_name:
            self.status_label.setText("Please enter a target table name.")
            self.status_label.setStyleSheet("color: red; background-color: transparent; border: none;")
            return

        # Reject a name that cannot be safely quoted before the task starts,
        # rather than failing part-way through the upload.
        try:
            quote_qualified_name(table_name)
        except ValueError as exc:
            self.status_label.setText(str(exc))
            self.status_label.setStyleSheet("color: red; background-color: transparent; border: none;")
            return

        # Advisory: a name should be at least catalog.db.table. This does not
        # block the upload, so it is carried into the progress message rather
        # than being set and then immediately overwritten by it.
        advisory = ""
        if len(table_name.split(".")) < 2:
            advisory = (
                " Note: table name is not fully qualified "
                "(e.g., catalog.database.table)."
            )

        self.upload_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Uploading layer..." + advisory)
        self.status_label.setStyleSheet(
            ("color: orange; " if advisory else "color: gray; ")
            + "background-color: transparent; border: none;"
        )

        self._upload_task = UploadTask(layer, table_name, self.conn_mgr)
        self._upload_task.taskCompleted.connect(self._on_upload_success)
        self._upload_task.taskTerminated.connect(self._on_upload_error)
        QgsApplication.taskManager().addTask(self._upload_task)

    def _on_cancel(self):
        if self._upload_task:
            self._upload_task.cancel()

    def cancel_running_task(self):
        """Cancel any running task and reset UI. Called on disconnect."""
        if self._upload_task:
            self._upload_task.cancel()
            self._upload_task = None
        self._reset_ui()

    def _reset_ui(self):
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.upload_btn.setEnabled(True)

    def _on_upload_success(self):
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.upload_btn.setEnabled(True)
        table_name = self.table_name_input.text().strip()
        count = self._upload_task.statements_executed - 1  # minus CREATE TABLE
        self.status_label.setText(
            f"Successfully uploaded to '{table_name}' ({count} batch(es))"
        )
        self.status_label.setStyleSheet("color: green; background-color: transparent; border: none;")

    def _on_upload_error(self):
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.upload_btn.setEnabled(True)
        if self._upload_task and self._upload_task.isCanceled():
            self.status_label.setText("Upload cancelled.")
            self.status_label.setStyleSheet("color: orange; background-color: transparent; border: none;")
        else:
            error = self._upload_task.error_message if self._upload_task else "Unknown error"
            self.status_label.setText(f"Upload error: {error}")
            self.status_label.setStyleSheet("color: red; background-color: transparent; border: none;")
