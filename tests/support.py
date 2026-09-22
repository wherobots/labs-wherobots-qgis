"""Test support: stub the QGIS/PyQt runtime and control dependency presence.

The plugin modules import ``qgis.PyQt`` and ``qgis.core`` at import time, which
are only available inside a running QGIS. These stubs provide just enough
surface for the pure-Python logic layers (``core.connection`` and
``core.query_task``) to import and run under plain pytest.
"""

import importlib
import os
import sys
import types

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FakeSignal:
    """Minimal stand-in for a bound pyqtSignal: records/relays emissions."""

    def __init__(self, *args):
        self._subscribers = []
        self.emissions = []

    def connect(self, fn):
        self._subscribers.append(fn)

    def emit(self, *args):
        self.emissions.append(args)
        for fn in list(self._subscribers):
            fn(*args)


def install_qgis_stubs():
    """Register fake ``qgis`` modules in sys.modules (idempotent)."""
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)

    if "qgis" in sys.modules:
        return

    qgis = types.ModuleType("qgis")
    pyqt = types.ModuleType("qgis.PyQt")
    qtcore = types.ModuleType("qgis.PyQt.QtCore")
    qtwidgets = types.ModuleType("qgis.PyQt.QtWidgets")
    qtgui = types.ModuleType("qgis.PyQt.QtGui")
    qgis_core = types.ModuleType("qgis.core")

    class QObject:
        def __init__(self, parent=None):
            self._parent = parent

    class _Qt:
        # Scoped forms (Qt6 / PyQt5 5.15) used by the plugin code.
        class DockWidgetArea:
            RightDockWidgetArea = 2

        class TextInteractionFlag:
            TextSelectableByMouse = 1

        # Flat forms kept for any legacy references.
        TextSelectableByMouse = 1
        RightDockWidgetArea = 2

    class QVariant:
        # Qt5-style QVariant.Type members (absent on Qt6 → drives qt_compat).
        Int = 2
        LongLong = 4
        Double = 6
        String = 10
        Bool = 1
        Date = 14
        DateTime = 16

    class QMetaType:
        class Type:
            Int = 2
            LongLong = 4
            Double = 6
            QString = 10
            Bool = 1
            QDate = 14
            QDateTime = 16

    class QgsWkbTypes:
        Unknown = 0
        NoGeometry = 100

        @staticmethod
        def displayString(_t):
            return "Point"

    class QgsTask:
        CanCancel = 1

        def __init__(self, description="", flags=0):
            self.description = description

    class QgsSettings:
        """In-memory stand-in. The backing store is class-level so separate
        instances share state — mirroring QgsSettings' process-global backing
        and letting tests simulate closing/reopening the plugin."""

        _store = {}

        def value(self, key, default=None, type=None):
            val = QgsSettings._store.get(key, default)
            if type is bool and not isinstance(val, bool):
                if isinstance(val, str):
                    return val.strip().lower() in ("1", "true", "yes")
                return bool(val)
            return val

        def setValue(self, key, value):
            QgsSettings._store[key] = value

        def remove(self, key):
            QgsSettings._store.pop(key, None)

    class QIcon:
        def __init__(self, path=""):
            self.path = path

        def isNull(self):
            return not bool(self.path)

    class QAction:
        def __init__(self, icon=None, text="", parent=None):
            self.icon = icon
            self.text = text
            self.object_name = ""
            self.tool_tip = ""
            self.status_tip = ""
            self.checkable = False
            self.checked = False
            self.triggered = FakeSignal()

        def setObjectName(self, name):
            self.object_name = name

        def setToolTip(self, text):
            self.tool_tip = text

        def setStatusTip(self, text):
            self.status_tip = text

        def setCheckable(self, value):
            self.checkable = value

        def setChecked(self, value):
            self.checked = bool(value)

        def isChecked(self):
            return self.checked

    class Qgis:
        Info = 0
        Warning = 1
        Critical = 2

    class QgsMessageLog:
        """Captures messages so tests can assert a failure was recorded."""

        messages = []

        @staticmethod
        def logMessage(message, tag="", level=0):
            QgsMessageLog.messages.append((message, tag, level))

    qtcore.QObject = QObject
    qtcore.pyqtSignal = lambda *a, **k: FakeSignal()
    qtcore.Qt = _Qt
    qtcore.QVariant = QVariant
    qtcore.QMetaType = QMetaType
    qtwidgets.QAction = QAction
    qtgui.QIcon = QIcon
    qgis_core.QgsTask = QgsTask
    qgis_core.QgsSettings = QgsSettings
    qgis_core.QgsWkbTypes = QgsWkbTypes
    qgis_core.Qgis = Qgis
    qgis_core.QgsMessageLog = QgsMessageLog

    qgis.PyQt = pyqt
    pyqt.QtCore = qtcore
    pyqt.QtWidgets = qtwidgets
    pyqt.QtGui = qtgui

    sys.modules.update(
        {
            "qgis": qgis,
            "qgis.PyQt": pyqt,
            "qgis.PyQt.QtCore": qtcore,
            "qgis.PyQt.QtWidgets": qtwidgets,
            "qgis.PyQt.QtGui": qtgui,
            "qgis.core": qgis_core,
        }
    )


def reset_qgs_settings():
    """Clear the in-memory QgsSettings store between tests."""
    install_qgis_stubs()
    sys.modules["qgis.core"].QgsSettings._store.clear()


def logged_messages():
    """Messages captured by the stub QgsMessageLog since the last clear."""
    install_qgis_stubs()
    return sys.modules["qgis.core"].QgsMessageLog.messages


def clear_logged_messages():
    install_qgis_stubs()
    sys.modules["qgis.core"].QgsMessageLog.messages.clear()


class _DbapiBlocker:
    """A meta-path finder that makes ``wherobots`` imports fail."""

    def find_spec(self, name, path=None, target=None):
        if name == "wherobots" or name.startswith("wherobots."):
            raise ModuleNotFoundError(f"blocked for test: {name}")
        return None


def _purge(*prefixes):
    for name in list(sys.modules):
        if any(name == p or name.startswith(p + ".") for p in prefixes):
            del sys.modules[name]


def dbapi_installed():
    """Whether wherobots-python-dbapi is actually importable in this env."""
    try:
        return importlib.util.find_spec("wherobots.db") is not None
    except (ImportError, ValueError):
        return False


def load_connection(*, available):
    """Import a fresh copy of ``core.connection`` with the dependency present
    (``available=True``) or forcibly absent (``available=False``)."""
    install_qgis_stubs()
    _purge("wherobots_qgis")  # force connection.py to re-execute its guard

    if available:
        return importlib.import_module("wherobots_qgis.core.connection")

    _purge("wherobots")
    blocker = _DbapiBlocker()
    sys.meta_path.insert(0, blocker)
    try:
        return importlib.import_module("wherobots_qgis.core.connection")
    finally:
        sys.meta_path.remove(blocker)
