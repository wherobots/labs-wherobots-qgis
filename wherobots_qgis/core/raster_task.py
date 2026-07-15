import base64
import os
import tempfile

from qgis.core import QgsTask

from ..utils.qt_compat import TASK_CAN_CANCEL

# GeoTIFF magic bytes: little-endian ("II" + version 42) or big-endian ("MM" + version 42)
_TIFF_LE_MAGIC = b"\x49\x49\x2a\x00"
_TIFF_BE_MAGIC = b"\x4d\x4d\x00\x2a"


def _to_bytes(val):
    """Try to convert a value to raw bytes. Returns bytes or None."""
    if isinstance(val, (bytes, bytearray)):
        return bytes(val)
    if isinstance(val, str):
        # Try base64 decoding (WebSocket JSON transport often encodes binary this way)
        try:
            decoded = base64.b64decode(val, validate=True)
            if len(decoded) >= 4:
                return decoded
        except Exception:
            pass
        # Try hex decoding (some drivers return hex strings)
        if all(c in "0123456789abcdefABCDEF" for c in val[:32]) and len(val) > 8:
            try:
                decoded = bytes.fromhex(val)
                if len(decoded) >= 4:
                    return decoded
            except Exception:
                pass
    # numpy bytes_ or objects with tobytes()
    if hasattr(val, "tobytes"):
        try:
            return val.tobytes()
        except Exception:
            pass
    return None


def _is_geotiff(data):
    """Check if raw bytes start with TIFF magic bytes."""
    if data and len(data) >= 4:
        return data[:4] == _TIFF_LE_MAGIC or data[:4] == _TIFF_BE_MAGIC
    return False


class RasterTask(QgsTask):
    """Background task that executes a raster SQL query against Wherobots.

    Detects binary GeoTIFF columns in results (from RS_AsGeoTiff) and
    writes them to temporary files for loading as QgsRasterLayer.
    Non-binary results are returned as a DataFrame for memory layer display.
    """

    def __init__(self, sql, connection_manager, description="Running raster query"):
        super().__init__(description, TASK_CAN_CANCEL)
        self.sql = sql
        self.conn_mgr = connection_manager
        self.columns = None
        self.result_df = None
        self.geotiff_paths = []  # list of temp file paths with GeoTIFF data
        self.error_message = None
        self.debug_info = ""  # diagnostic info when detection fails

    def run(self):
        try:
            cursor = self.conn_mgr.get_cursor()
            cursor.execute(self.sql)
            self.columns = [desc[0] for desc in cursor.description] if cursor.description else []
            self.result_df = cursor.fetchall()

            if self.result_df is not None and not self.result_df.empty:
                self._extract_geotiffs()

            return True
        except Exception as e:
            self.error_message = str(e)
            return False

    def _extract_geotiffs(self):
        """Check for columns containing GeoTIFF data and write to temp files.

        Handles multiple encodings: raw bytes, base64 strings, hex strings,
        and numpy byte objects.
        """
        tmp_dir = tempfile.mkdtemp(prefix="wherobots_raster_")

        for col in self.result_df.columns:
            # Check first non-null value in the column
            for val in self.result_df[col]:
                if val is None:
                    continue

                raw = _to_bytes(val)
                if raw and _is_geotiff(raw):
                    # This column has GeoTIFF data — write each row
                    for i, row_val in enumerate(self.result_df[col]):
                        if self.isCanceled():
                            return
                        if row_val is None:
                            continue
                        row_bytes = _to_bytes(row_val)
                        if row_bytes:
                            path = os.path.join(tmp_dir, f"raster_{col}_{i}.tif")
                            with open(path, "wb") as f:
                                f.write(row_bytes)
                            self.geotiff_paths.append(path)
                elif raw:
                    # Binary data but not GeoTIFF — still try writing it
                    for i, row_val in enumerate(self.result_df[col]):
                        if self.isCanceled():
                            return
                        if row_val is None:
                            continue
                        row_bytes = _to_bytes(row_val)
                        if row_bytes:
                            path = os.path.join(tmp_dir, f"raster_{col}_{i}.tif")
                            with open(path, "wb") as f:
                                f.write(row_bytes)
                            self.geotiff_paths.append(path)
                else:
                    # Record debug info for the first non-null value
                    val_type = type(val).__name__
                    val_preview = repr(val)[:200]
                    self.debug_info = (
                        f"Column '{col}': type={val_type}, preview={val_preview}"
                    )
                break  # only check first non-null value per column

    def finished(self, result):
        pass
