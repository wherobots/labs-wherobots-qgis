"""Qt5 / Qt6 compatibility shim for running on both QGIS 3.x and QGIS 4.0.

QGIS 4.0 moves to Qt6 / PyQt6. Most of this plugin is already forward
compatible because it imports Qt through the ``qgis.PyQt`` layer and uses
scoped enums. Two differences cannot be expressed as a single literal and are
centralised here:

1. Field types. ``QVariant.Int`` and friends were removed in Qt6 in favour of
   ``QMetaType.Type.*``. But the ``QMetaType``-based ``QgsField`` constructor
   only exists since QGIS 3.38, while the ``QVariant`` one is still present on
   every Qt5 build. So on Qt5 (all supported QGIS 3.x) we use ``QVariant`` and
   on Qt6 (QGIS 4.0) we use ``QMetaType`` — keyed off which enum actually
   exists, which cleanly spans QGIS 3.22 → 4.0.

2. Some QGIS enums (``QgsTask.Flag``, ``QgsWkbTypes.Type``) are only reachable
   unscoped on older bindings and only scoped under PyQt6. ``_member`` resolves
   whichever form is present.
"""

from qgis.PyQt.QtCore import QVariant

try:  # QMetaType lives in QtCore on both Qt5 and Qt6; guard just in case.
    from qgis.PyQt.QtCore import QMetaType
except ImportError:  # pragma: no cover - QMetaType is present on all targets
    QMetaType = None

from qgis.core import QgsTask, QgsWkbTypes


def _member(cls, scope, name):
    """Return an enum member that may be scoped (Qt6 / recent QGIS) or flat
    (older Qt5 bindings). Falls back to the flat attribute on ``cls``."""
    holder = getattr(cls, scope, cls)
    return getattr(holder, name)


# True on Qt5 (QVariant.Type still present), False on Qt6 (removed).
USE_QVARIANT_TYPES = hasattr(QVariant, "String")

if USE_QVARIANT_TYPES:
    FIELD_INT = QVariant.Int
    FIELD_LONGLONG = QVariant.LongLong
    FIELD_DOUBLE = QVariant.Double
    FIELD_STRING = QVariant.String
    FIELD_BOOL = QVariant.Bool
    FIELD_DATE = QVariant.Date
    FIELD_DATETIME = QVariant.DateTime
else:
    _t = QMetaType.Type
    FIELD_INT = _t.Int
    FIELD_LONGLONG = _t.LongLong
    FIELD_DOUBLE = _t.Double
    FIELD_STRING = _t.QString
    FIELD_BOOL = _t.Bool
    FIELD_DATE = _t.QDate
    FIELD_DATETIME = _t.QDateTime


# QgsTask flags and WKB type members, resolved for whichever binding is running.
TASK_CAN_CANCEL = _member(QgsTask, "Flag", "CanCancel")
WKB_UNKNOWN = _member(QgsWkbTypes, "Type", "Unknown")
WKB_NO_GEOMETRY = _member(QgsWkbTypes, "Type", "NoGeometry")
