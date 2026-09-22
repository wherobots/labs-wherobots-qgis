"""Plugin logging helpers.

Failures that the plugin recovers from used to be swallowed silently, which
left no trace for the user or for anyone debugging a support report. These
helpers route them to the QGIS Log Messages panel under a "Wherobots" tab.

The QGIS imports are guarded so the pure-Python parts of the plugin remain
importable under test harnesses that only stub part of the QGIS API.
"""

LOG_TAG = "Wherobots"

try:
    from qgis.core import Qgis, QgsMessageLog

    _INFO = Qgis.Info
    _WARNING = Qgis.Warning
except Exception:  # pragma: no cover - only hit outside a QGIS runtime
    QgsMessageLog = None
    _INFO = None
    _WARNING = None


# Messages the sink could not accept. The handler below cannot log its own
# failure, so it counts instead of discarding silently — ``dropped_count()``
# answers "did anything get lost?" from the QGIS Python console.
_dropped = 0


def dropped_count():
    """Number of messages the QGIS log sink refused since plugin load."""
    return _dropped


def _log(message, level):
    if QgsMessageLog is None:
        return
    try:
        QgsMessageLog.logMessage(str(message), LOG_TAG, level)
    except Exception:
        # A logging sink must never be the thing that breaks its caller: the
        # C++ side may already be torn down when a close failure is logged
        # during plugin unload. Nothing useful can be raised or logged from
        # here, so record that the message was lost.
        global _dropped
        _dropped += 1


def log_warning(message):
    """Record a recovered-from failure the user may need to know about."""
    _log(message, _WARNING)


def log_debug(message):
    """Record diagnostic detail that is only interesting when investigating."""
    _log(message, _INFO)
