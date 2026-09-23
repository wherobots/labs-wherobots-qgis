"""Tests for the Qt5/Qt6 compatibility shim (QGIS 3.x <-> QGIS 4.0).

Verifies the field-type selection picks QVariant on Qt5 and QMetaType on Qt6,
and that the QGIS-native enum members resolve on either binding.
"""

import importlib
import sys

from tests.support import install_qgis_stubs

install_qgis_stubs()


def _load_qt_compat():
    sys.modules.pop("wherobots_qgis.utils.qt_compat", None)
    return importlib.import_module("wherobots_qgis.utils.qt_compat")


# --- Qt5 path (QVariant.Type present) ---------------------------------------

def test_qt5_path_uses_qvariant_types():
    compat = _load_qt_compat()
    from qgis.PyQt.QtCore import QVariant

    assert compat.USE_QVARIANT_TYPES is True
    assert compat.FIELD_STRING == QVariant.String
    assert compat.FIELD_INT == QVariant.Int
    assert compat.FIELD_DATETIME == QVariant.DateTime


def test_qgis_native_enums_resolve_with_fallback():
    """QgsTask.Flag / QgsWkbTypes.Type are absent on the flat stub, so the
    shim must fall back to the unscoped members."""
    compat = _load_qt_compat()
    assert compat.TASK_CAN_CANCEL == 1      # QgsTask.CanCancel
    assert compat.WKB_UNKNOWN == 0          # QgsWkbTypes.Unknown
    assert compat.WKB_NO_GEOMETRY == 100    # QgsWkbTypes.NoGeometry


# --- Qt6 path (QVariant.Type removed -> QMetaType.Type) ----------------------

def test_qt6_path_uses_qmetatype(monkeypatch):
    qtcore = sys.modules["qgis.PyQt.QtCore"]

    class QVariantQt6:  # PyQt6 QVariant has no Type members
        pass

    monkeypatch.setattr(qtcore, "QVariant", QVariantQt6)
    compat = _load_qt_compat()

    assert compat.USE_QVARIANT_TYPES is False
    assert compat.FIELD_STRING == qtcore.QMetaType.Type.QString
    assert compat.FIELD_INT == qtcore.QMetaType.Type.Int
    assert compat.FIELD_DATE == qtcore.QMetaType.Type.QDate

    # Leave the module cache in the default (Qt5) state for other tests.
    monkeypatch.undo()
    _load_qt_compat()


def test_scoped_qgis_enums_preferred_when_present(monkeypatch):
    """When a binding exposes the scoped enum class (as PyQt6 does), the shim
    must use it rather than the flat attribute."""
    qgis_core = sys.modules["qgis.core"]

    class QgsWkbTypesQt6:
        class Type:
            Unknown = 4001
            NoGeometry = 4002

    monkeypatch.setattr(qgis_core, "QgsWkbTypes", QgsWkbTypesQt6)
    compat = _load_qt_compat()

    assert compat.WKB_UNKNOWN == 4001
    assert compat.WKB_NO_GEOMETRY == 4002

    monkeypatch.undo()
    _load_qt_compat()


# --- task_is_alive ----------------------------------------------------------
#
# Regression guard for the crash seen in QGIS 4 after a query finished and the
# user then disconnected:
#
#   File "gui/query_tab.py", in cancel_running_task
#     self._query_task.cancel()
#   RuntimeError: wrapped C/C++ object of type QueryTask has been deleted
#
# The task manager owns the task and destroys it on completion, leaving the
# tab holding a stale wrapper.

def test_none_is_not_alive():
    compat = _load_qt_compat()
    assert compat.task_is_alive(None) is False


def test_a_live_task_is_alive():
    compat = _load_qt_compat()
    from qgis.core import QgsTask

    assert compat.task_is_alive(QgsTask("running")) is True


def test_a_deleted_task_is_not_alive(monkeypatch):
    """The case that produced the traceback: the wrapper outlives the C++ object."""
    compat = _load_qt_compat()
    from qgis.core import QgsTask

    task = QgsTask("finished")

    class FakeSip:
        @staticmethod
        def isdeleted(obj):
            return obj is task

    monkeypatch.setattr(compat, "sip", FakeSip)
    assert compat.task_is_alive(task) is False
    assert compat.task_is_alive(QgsTask("other")) is True


def test_missing_sip_does_not_break_the_check(monkeypatch):
    """Bindings without sip fall back to treating a non-None task as usable."""
    compat = _load_qt_compat()
    from qgis.core import QgsTask

    monkeypatch.setattr(compat, "sip", None)
    assert compat.task_is_alive(QgsTask("running")) is True
    assert compat.task_is_alive(None) is False
