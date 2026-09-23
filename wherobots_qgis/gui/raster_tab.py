from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QTextEdit,
    QPushButton,
    QLabel,
    QLineEdit,
    QGroupBox,
    QProgressBar,
    QFormLayout,
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsApplication

from qgis.core import QgsRasterLayer

from ..core.connection import ConnectionManager
from ..core.raster_task import RasterTask
from ..utils.qt_compat import task_is_alive
from ..utils.layer_utils import (
    results_to_memory_layer,
    add_layer_to_project,
    get_map_extent_bounds,
)


class RasterTab(QWidget):
    """Tab for querying raster data from Wherobots and loading into QGIS.

    Provides a SQL editor for raster queries with RS_ functions,
    bounding box controls, and loads results as raster or vector layers.
    """

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.conn_mgr = ConnectionManager.instance()
        self._raster_task = None
        self._query_counter = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)

        # --- SQL editor ---
        query_group = QGroupBox("Raster SQL Query")
        query_layout = QVBoxLayout()
        self.sql_editor = QPlainTextEdit()
        self.sql_editor.setPlaceholderText(
            "Enter raster SQL query...\n\n"
            "Load raster into map (use RS_AsGeoTiff):\n"
            "SELECT RS_AsGeoTiff(rast) FROM my_raster_table\n"
            "WHERE RS_Intersects(rast, ST_GeomFromWKT('...'))\n\n"
            "Get pixel values:\n"
            "SELECT RS_Values(rast, Array(ST_Point(-122.4, 37.8)))\n"
            "FROM my_raster_table"
        )
        self.sql_editor.setMinimumHeight(100)
        query_layout.addWidget(self.sql_editor)
        query_group.setLayout(query_layout)
        layout.addWidget(query_group)

        # --- Bounding box ---
        bbox_group = QGroupBox("Spatial Extent")
        bbox_layout = QVBoxLayout()

        self.use_extent_btn = QPushButton("Use Current Map Extent")
        bbox_layout.addWidget(self.use_extent_btn)

        coords_layout = QFormLayout()
        self.xmin_input = QLineEdit()
        self.ymin_input = QLineEdit()
        self.xmax_input = QLineEdit()
        self.ymax_input = QLineEdit()
        for inp in [self.xmin_input, self.ymin_input, self.xmax_input, self.ymax_input]:
            inp.setPlaceholderText("0.0")
        coords_layout.addRow("X Min (West):", self.xmin_input)
        coords_layout.addRow("Y Min (South):", self.ymin_input)
        coords_layout.addRow("X Max (East):", self.xmax_input)
        coords_layout.addRow("Y Max (North):", self.ymax_input)
        bbox_layout.addLayout(coords_layout)

        self.insert_bbox_btn = QPushButton("Insert Extent into Query")
        bbox_layout.addWidget(self.insert_bbox_btn)

        bbox_group.setLayout(bbox_layout)
        layout.addWidget(bbox_group)

        # --- Execute / Cancel ---
        btn_layout = QHBoxLayout()
        self.execute_btn = QPushButton("Execute Raster Query")
        self.execute_btn.setMinimumHeight(36)
        self.execute_btn.setStyleSheet(
            "QPushButton { background-color: #9333ea; color: white; font-weight: bold; }"
            "QPushButton:disabled { background-color: #c4b5fd; }"
        )
        btn_layout.addWidget(self.execute_btn)

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
        self.use_extent_btn.clicked.connect(self._on_use_extent)
        self.insert_bbox_btn.clicked.connect(self._on_insert_bbox)
        self.execute_btn.clicked.connect(self._on_execute)
        self.cancel_btn.clicked.connect(self._on_cancel)

    def _on_use_extent(self):
        """Fill bounding box fields from current map canvas extent."""
        try:
            xmin, ymin, xmax, ymax = get_map_extent_bounds(self.iface)
            self.xmin_input.setText(f"{xmin:.6f}")
            self.ymin_input.setText(f"{ymin:.6f}")
            self.xmax_input.setText(f"{xmax:.6f}")
            self.ymax_input.setText(f"{ymax:.6f}")
        except Exception as e:
            self.status_label.setText(f"Could not get map extent: {e}")
            self.status_label.setStyleSheet("color: red; background-color: transparent; border: none;")

    def _get_extent_wkt(self):
        """Build a WKT polygon from the bounding box fields."""
        try:
            xmin = float(self.xmin_input.text())
            ymin = float(self.ymin_input.text())
            xmax = float(self.xmax_input.text())
            ymax = float(self.ymax_input.text())
        except (ValueError, TypeError):
            return None
        return (
            f"POLYGON(({xmin} {ymin}, {xmax} {ymin}, "
            f"{xmax} {ymax}, {xmin} {ymax}, {xmin} {ymin}))"
        )

    def _on_insert_bbox(self):
        """Insert the bounding box as a ST_GeomFromWKT clause into the SQL editor."""
        wkt = self._get_extent_wkt()
        if not wkt:
            self.status_label.setText("Enter valid bounding box coordinates first.")
            self.status_label.setStyleSheet("color: red; background-color: transparent; border: none;")
            return
        clause = f"ST_GeomFromWKT('{wkt}')"
        cursor = self.sql_editor.textCursor()
        cursor.insertText(clause)

    def _on_execute(self):
        sql = self.sql_editor.toPlainText().strip()
        if not sql:
            self.status_label.setText("Please enter a raster query.")
            self.status_label.setStyleSheet("color: red; background-color: transparent; border: none;")
            return

        self.execute_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Executing raster query...")
        self.status_label.setStyleSheet("color: gray; background-color: transparent; border: none;")

        self._raster_task = RasterTask(sql, self.conn_mgr)
        self._raster_task.taskCompleted.connect(self._on_query_success)
        self._raster_task.taskTerminated.connect(self._on_query_error)
        QgsApplication.taskManager().addTask(self._raster_task)

    def _on_cancel(self):
        if task_is_alive(self._raster_task):
            self._raster_task.cancel()

    def cancel_running_task(self):
        """Cancel any running task and reset UI. Called on disconnect."""
        if task_is_alive(self._raster_task):
            self._raster_task.cancel()
        self._raster_task = None
        self._reset_ui()

    def _reset_ui(self):
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.execute_btn.setEnabled(True)

    def _on_query_success(self):
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.execute_btn.setEnabled(True)

        # The task manager destroys the task once it has finished, so take the
        # reference and drop ours here rather than leaving a stale wrapper for
        # a later cancel to trip over.
        task = self._raster_task
        self._raster_task = None
        if not task_is_alive(task):
            return

        self._query_counter += 1

        # If we got GeoTIFF binary data, load as raster layers
        if task.geotiff_paths:
            loaded = 0
            for path in task.geotiff_paths:
                layer_name = f"Wherobots Raster {self._query_counter}"
                if len(task.geotiff_paths) > 1:
                    layer_name += f" ({loaded + 1})"
                layer = QgsRasterLayer(path, layer_name, "gdal")
                if layer.isValid():
                    add_layer_to_project(layer)
                    loaded += 1
            if loaded > 0:
                self.status_label.setText(
                    f"Loaded {loaded} raster layer(s) from GeoTIFF data"
                )
                self.status_label.setStyleSheet("color: green; background-color: transparent; border: none;")
            else:
                self.status_label.setText("GeoTIFF data received but could not load as raster layers.")
                self.status_label.setStyleSheet("color: orange; background-color: transparent; border: none;")
            return

        # Otherwise, treat as tabular results (metadata, pixel values, etc.)
        layer_name = f"Wherobots Raster {self._query_counter}"
        if task.result_df is not None and not task.result_df.empty:
            # Show debug info if binary detection failed
            debug_suffix = ""
            if task.debug_info:
                debug_suffix = f"\n\nRaster detection note: {task.debug_info}"

            layer = results_to_memory_layer(task.result_df, layer_name=layer_name)
            if layer.isValid():
                add_layer_to_project(layer)
                self.status_label.setText(
                    f"Loaded {len(task.result_df)} result rows as '{layer_name}'"
                    f" (no raster data detected){debug_suffix}"
                )
                self.status_label.setStyleSheet("color: green; background-color: transparent; border: none;")
            else:
                self.status_label.setText(
                    f"Results returned but could not create layer.{debug_suffix}"
                )
                self.status_label.setStyleSheet("color: orange; background-color: transparent; border: none;")
        else:
            self.status_label.setText("Query returned no results.")
            self.status_label.setStyleSheet("color: orange; background-color: transparent; border: none;")

    def _on_query_error(self):
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.execute_btn.setEnabled(True)
        task = self._raster_task
        self._raster_task = None
        if task_is_alive(task) and task.isCanceled():
            self.status_label.setText("Raster query cancelled.")
            self.status_label.setStyleSheet("color: orange; background-color: transparent; border: none;")
        else:
            error = task.error_message if task_is_alive(task) else "Unknown error"
            self.status_label.setText(f"Error: {error}")
            self.status_label.setStyleSheet("color: red; background-color: transparent; border: none;")
