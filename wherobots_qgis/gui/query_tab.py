from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QTextEdit,
    QPushButton,
    QLabel,
    QSpinBox,
    QCheckBox,
    QLineEdit,
    QComboBox,
    QRadioButton,
    QButtonGroup,
    QGroupBox,
    QProgressBar,
    QStackedWidget,
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsApplication, QgsProject

from ..core.connection import ConnectionManager
from ..core.query_task import QueryTask, BrowseTablesTask
from ..utils.layer_utils import (
    results_to_memory_layer,
    add_layer_to_project,
    get_map_extent_wkt,
)
from ..utils.settings import PluginSettings
from ..utils.sql import (
    escape_string_literal,
    quote_column,
    quote_qualified_name,
)


class QueryTab(QWidget):
    """SQL query tab with free-form editor or table browser mode.

    Supports max row limit, spatial extent filtering, and renders
    results as QGIS map layers.
    """

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.conn_mgr = ConnectionManager.instance()
        self.settings = PluginSettings()
        self._query_task = None
        self._browse_task = None
        self._query_counter = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)

        # --- Mode toggle ---
        mode_group = QGroupBox("Query Mode")
        mode_layout = QHBoxLayout()
        self.free_query_radio = QRadioButton("Free Query")
        self.browse_radio = QRadioButton("Browse Tables")
        self.free_query_radio.setChecked(True)
        mode_group_btns = QButtonGroup(self)
        mode_group_btns.addButton(self.free_query_radio)
        mode_group_btns.addButton(self.browse_radio)
        mode_layout.addWidget(self.free_query_radio)
        mode_layout.addWidget(self.browse_radio)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # --- Stacked widget for the two modes ---
        self.mode_stack = QStackedWidget()

        # Page 0: Free query editor
        free_page = QWidget()
        free_layout = QVBoxLayout()
        free_layout.setContentsMargins(0, 0, 0, 0)
        self.sql_editor = QPlainTextEdit()
        self.sql_editor.setPlaceholderText(
            "Enter SQL query...\n\n"
            "Example:\n"
            "SELECT * FROM wherobots_open_data.overture_maps_foundation.places_place\n"
            "LIMIT 100"
        )
        self.sql_editor.setMinimumHeight(120)
        free_layout.addWidget(self.sql_editor)
        free_page.setLayout(free_layout)
        self.mode_stack.addWidget(free_page)

        # Page 1: Browse tables
        browse_page = QWidget()
        browse_layout = QVBoxLayout()
        browse_layout.setContentsMargins(0, 0, 0, 0)

        schema_row = QHBoxLayout()
        schema_row.addWidget(QLabel("Schema:"))
        self.schema_combo = QComboBox()
        self.schema_combo.setEditable(True)
        self.schema_combo.setPlaceholderText("e.g., wherobots_open_data")
        schema_row.addWidget(self.schema_combo)
        self.load_schemas_btn = QPushButton("Load")
        self.load_schemas_btn.setMaximumWidth(60)
        schema_row.addWidget(self.load_schemas_btn)
        browse_layout.addLayout(schema_row)

        table_row = QHBoxLayout()
        table_row.addWidget(QLabel("Table:"))
        self.table_combo = QComboBox()
        self.table_combo.setEditable(True)
        self.table_combo.setPlaceholderText("Select a table")
        table_row.addWidget(self.table_combo)
        self.load_tables_btn = QPushButton("Load")
        self.load_tables_btn.setMaximumWidth(60)
        table_row.addWidget(self.load_tables_btn)
        browse_layout.addLayout(table_row)

        browse_page.setLayout(browse_layout)
        self.mode_stack.addWidget(browse_page)
        layout.addWidget(self.mode_stack)

        # --- Query options ---
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()

        row_limit_layout = QHBoxLayout()
        row_limit_layout.addWidget(QLabel("Max rows:"))
        self.max_rows_spin = QSpinBox()
        self.max_rows_spin.setRange(1, 1000)
        self.max_rows_spin.setValue(self.settings.get_default_max_rows())
        row_limit_layout.addWidget(self.max_rows_spin)
        row_limit_layout.addStretch()
        options_layout.addLayout(row_limit_layout)

        # Spatial extent filter — persisted between plugin openings.
        self.extent_checkbox = QCheckBox("Filter by current map extent")
        self.extent_checkbox.setChecked(self.settings.get_filter_by_extent())
        options_layout.addWidget(self.extent_checkbox)

        geom_col_layout = QHBoxLayout()
        geom_col_layout.addWidget(QLabel("Geometry column:"))
        self.geom_col_input = QLineEdit(self.settings.get_geometry_column())
        self.geom_col_input.setEnabled(self.extent_checkbox.isChecked())
        geom_col_layout.addWidget(self.geom_col_input)
        options_layout.addLayout(geom_col_layout)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # --- Execute / Cancel buttons ---
        btn_layout = QHBoxLayout()
        self.execute_btn = QPushButton("Execute Query")
        self.execute_btn.setMinimumHeight(36)
        self.execute_btn.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: white; font-weight: bold; }"
            "QPushButton:disabled { background-color: #93c5fd; }"
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

        # --- Progress bar ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # indeterminate
        layout.addWidget(self.progress_bar)

        # --- Status output ---
        self.status_label = QTextEdit()
        self.status_label.setReadOnly(True)
        self.status_label.setMaximumHeight(80)
        self.status_label.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(self.status_label)

        layout.addStretch()
        self.setLayout(layout)

        # --- Signals ---
        self.free_query_radio.toggled.connect(self._on_mode_changed)
        self.extent_checkbox.toggled.connect(self.geom_col_input.setEnabled)
        # Persist the extent filter so it survives closing/reopening the plugin.
        self.extent_checkbox.toggled.connect(self.settings.set_filter_by_extent)
        self.geom_col_input.textChanged.connect(self.settings.set_geometry_column)
        self.execute_btn.clicked.connect(self._on_execute)
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.load_schemas_btn.clicked.connect(self._on_load_schemas)
        self.load_tables_btn.clicked.connect(self._on_load_tables)

    def _on_mode_changed(self, free_checked):
        self.mode_stack.setCurrentIndex(0 if free_checked else 1)

    def _build_sql(self):
        """Build the final SQL from the current UI state.

        Free-form SQL is passed through as typed — this is a database client
        and arbitrary SQL is the point. Everything the plugin *constructs*
        around it (table names, the geometry column, the extent literal) is
        quoted, so a pasted name cannot change the shape of the statement.

        :raises ValueError: if a table name or geometry column is invalid
        """
        if self.free_query_radio.isChecked():
            sql = self.sql_editor.toPlainText().strip()
        else:
            table = self.table_combo.currentText().strip()
            if not table:
                return None
            sql = f"SELECT * FROM {quote_qualified_name(table)}"

        if not sql:
            return None

        # Append spatial extent filter
        if self.extent_checkbox.isChecked():
            geom_col = quote_column(self.geom_col_input.text().strip() or "geometry")
            extent_wkt = escape_string_literal(get_map_extent_wkt(self.iface))
            extent_clause = (
                f"ST_Intersects({geom_col}, ST_GeomFromWKT('{extent_wkt}'))"
            )
            # Check if there's already a WHERE clause
            sql_upper = sql.upper()
            if "WHERE" in sql_upper:
                # Insert before ORDER BY / LIMIT if present
                sql = sql + f" AND {extent_clause}"
            else:
                # Check if there's ORDER BY or LIMIT without WHERE
                for kw in ["ORDER BY", "GROUP BY", "HAVING", "LIMIT"]:
                    idx = sql_upper.find(kw)
                    if idx > 0:
                        sql = sql[:idx] + f"WHERE {extent_clause} " + sql[idx:]
                        break
                else:
                    sql = sql + f" WHERE {extent_clause}"

        # Append LIMIT if not already present
        max_rows = self.max_rows_spin.value()
        if "LIMIT" not in sql.upper():
            sql = sql + f" LIMIT {max_rows}"

        return sql

    def _on_execute(self):
        try:
            sql = self._build_sql()
        except ValueError as exc:
            self.status_label.setText(str(exc))
            self.status_label.setStyleSheet("color: red; background-color: transparent; border: none;")
            return
        if not sql:
            self.status_label.setText("Please enter a query or select a table.")
            self.status_label.setStyleSheet("color: red; background-color: transparent; border: none;")
            return

        self.execute_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Executing query...")
        self.status_label.setStyleSheet("color: gray; background-color: transparent; border: none;")

        max_rows = self.max_rows_spin.value()

        self._query_task = QueryTask(sql, self.conn_mgr, max_rows=max_rows)
        self._query_task.taskCompleted.connect(self._on_query_success)
        self._query_task.taskTerminated.connect(self._on_query_error)
        QgsApplication.taskManager().addTask(self._query_task)

    def _on_cancel(self):
        if self._query_task:
            self._query_task.cancel()

    def cancel_running_task(self):
        """Cancel any running task and reset UI. Called on disconnect."""
        if self._query_task:
            self._query_task.cancel()
            self._query_task = None
        self._reset_ui()

    def _reset_ui(self):
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.execute_btn.setEnabled(True)

    def _on_query_success(self):
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.execute_btn.setEnabled(True)

        task = self._query_task
        self._query_counter += 1
        layer_name = f"Wherobots Query {self._query_counter}"

        if task.result_df is not None and not task.result_df.empty:
            layer = results_to_memory_layer(task.result_df, layer_name=layer_name)
        else:
            self.status_label.setText("Query returned no results.")
            self.status_label.setStyleSheet("color: orange; background-color: transparent; border: none;")
            return

        if not layer.isValid():
            self.status_label.setText("Failed to create layer from results.")
            self.status_label.setStyleSheet("color: red; background-color: transparent; border: none;")
            return

        add_layer_to_project(layer)
        row_count = layer.featureCount()
        self.status_label.setText(f"Loaded {row_count} features as '{layer_name}'")
        self.status_label.setStyleSheet("color: green; background-color: transparent; border: none;")

    def _on_query_error(self):
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.execute_btn.setEnabled(True)
        if self._query_task and self._query_task.isCanceled():
            self.status_label.setText("Query cancelled.")
            self.status_label.setStyleSheet("color: orange; background-color: transparent; border: none;")
        else:
            error = self._query_task.error_message if self._query_task else "Unknown error"
            self.status_label.setText(f"Error: {error}")
            self.status_label.setStyleSheet("color: red; background-color: transparent; border: none;")

    def _on_load_schemas(self):
        schema = self.schema_combo.currentText().strip()
        try:
            sql = (
                f"SHOW SCHEMAS IN {quote_qualified_name(schema)}"
                if schema
                else "SHOW SCHEMAS"
            )
        except ValueError as exc:
            self.status_label.setText(str(exc))
            self.status_label.setStyleSheet("color: red; background-color: transparent; border: none;")
            return
        self._browse_task = BrowseTablesTask(self.conn_mgr, sql, "Loading schemas")
        self._browse_task.taskCompleted.connect(self._on_schemas_loaded)
        self._browse_task.taskTerminated.connect(self._on_browse_error)
        QgsApplication.taskManager().addTask(self._browse_task)

    def _on_schemas_loaded(self):
        task = self._browse_task
        self.schema_combo.clear()
        for row in task.results:
            # SHOW SCHEMAS returns rows with schema name as first column
            self.schema_combo.addItem(str(row[0]))
        if not task.results:
            self.status_label.setText("No schemas found.")
            self.status_label.setStyleSheet("color: orange; background-color: transparent; border: none;")

    def _on_load_tables(self):
        schema = self.schema_combo.currentText().strip()
        if not schema:
            self.status_label.setText("Enter a schema name first.")
            self.status_label.setStyleSheet("color: red; background-color: transparent; border: none;")
            return
        try:
            sql = f"SHOW TABLES IN {quote_qualified_name(schema)}"
        except ValueError as exc:
            self.status_label.setText(str(exc))
            self.status_label.setStyleSheet("color: red; background-color: transparent; border: none;")
            return
        self._browse_task = BrowseTablesTask(self.conn_mgr, sql, "Loading tables")
        self._browse_task.taskCompleted.connect(self._on_tables_loaded)
        self._browse_task.taskTerminated.connect(self._on_browse_error)
        QgsApplication.taskManager().addTask(self._browse_task)

    def _on_tables_loaded(self):
        task = self._browse_task
        self.table_combo.clear()
        schema = self.schema_combo.currentText().strip()
        for row in task.results:
            table_name = str(row[0])
            full_name = f"{schema}.{table_name}" if schema else table_name
            self.table_combo.addItem(full_name)
        if not task.results:
            self.status_label.setText("No tables found in this schema.")
            self.status_label.setStyleSheet("color: orange; background-color: transparent; border: none;")

    def _on_browse_error(self):
        error = self._browse_task.error_message if self._browse_task else "Unknown error"
        self.status_label.setText(f"Browse error: {error}")
        self.status_label.setStyleSheet("color: red; background-color: transparent; border: none;")
