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
    qgis_core = types.ModuleType("qgis.core")

    class QObject:
        def __init__(self, parent=None):
            self._parent = parent

    class _Qt:
        TextSelectableByMouse = 1

    class QgsTask:
        CanCancel = 1

        def __init__(self, description="", flags=0):
            self.description = description

    qtcore.QObject = QObject
    qtcore.pyqtSignal = lambda *a, **k: FakeSignal()
    qtcore.Qt = _Qt
    qgis_core.QgsTask = QgsTask

    qgis.PyQt = pyqt
    pyqt.QtCore = qtcore

    sys.modules.update(
        {
            "qgis": qgis,
            "qgis.PyQt": pyqt,
            "qgis.PyQt.QtCore": qtcore,
            "qgis.core": qgis_core,
        }
    )


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
