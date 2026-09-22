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


def _log(message, level):
    if QgsMessageLog is None:
        return
    try:
        QgsMessageLog.logMessage(str(message), LOG_TAG, level)
    except Exception:
        # Logging must never be the thing that breaks the caller.
        pass


def log_warning(message):
    """Record a recovered-from failure the user may need to know about."""
    _log(message, _WARNING)


def log_debug(message):
    """Record diagnostic detail that is only interesting when investigating."""
    _log(message, _INFO)
