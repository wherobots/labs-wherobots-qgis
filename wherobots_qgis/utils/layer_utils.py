import re
import json
import tempfile
import os

from qgis.core import (
    QgsVectorLayer,
    QgsRasterLayer,
    QgsProject,
    QgsFeature,
    QgsGeometry,
    QgsField,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFields,
    QgsWkbTypes,
    QgsJsonExporter,
)
from qgis.PyQt.QtCore import QVariant

# Regex to detect EWKT: optional "SRID=1234;" prefix followed by WKT geometry type
_EWKT_PATTERN = re.compile(
    r"^(SRID=\d+;)?\s*(POINT|LINESTRING|POLYGON|MULTIPOINT|MULTILINESTRING|"
    r"MULTIPOLYGON|GEOMETRYCOLLECTION)\s*[Z|M|ZM]?\s*\(",
    re.IGNORECASE,
)

# Map Python / DB-API types to QVariant types for QGIS fields
_TYPE_MAP = {
    "int": QVariant.Int,
    "int64": QVariant.LongLong,
    "int32": QVariant.Int,
    "float": QVariant.Double,
    "float64": QVariant.Double,
    "float32": QVariant.Double,
    "str": QVariant.String,
    "object": QVariant.String,
    "bool": QVariant.Bool,
    "NoneType": QVariant.String,
}


def _detect_geometry_column(columns, sample_row):
    """Find which column holds EWKT geometry data.

    :param columns: list of column name strings
    :param sample_row: dict or list of values for the first row
    """
    if sample_row is None:
        return None
    # sample_row can be a dict (from DataFrame.iloc) or list
    values = sample_row.values() if isinstance(sample_row, dict) else sample_row
    for i, val in enumerate(zip(columns, values)):
        col_name, cell = val
        if isinstance(cell, str) and _EWKT_PATTERN.match(cell.strip()):
            return col_name
    # Fallback: check column names
    geom_names = {"geometry", "geom", "wkt", "the_geom", "shape", "geo"}
    for col in columns:
        if col.lower() in geom_names:
            return col
    return None


def _parse_ewkt(ewkt_str):
    """Parse EWKT string, returning (QgsGeometry, srid)."""
    srid = 4326  # default
    text = ewkt_str.strip()
    if text.upper().startswith("SRID="):
        srid_part, text = text.split(";", 1)
        srid = int(srid_part.split("=")[1])
    geom = QgsGeometry.fromWkt(text.strip())
    return geom, srid


def _detect_geom_type_df(df, geom_col):
    """Detect the WKB geometry type from a DataFrame geometry column."""
    for val in df[geom_col]:
        if val and isinstance(val, str):
            geom, _ = _parse_ewkt(val)
            if not geom.isNull():
                return geom.wkbType()
    return QgsWkbTypes.Unknown


def _dtype_to_qvariant(dtype_str):
    """Map a Pandas dtype string to a QVariant type."""
    return _TYPE_MAP.get(str(dtype_str), QVariant.String)


def results_to_memory_layer(df, columns=None, layer_name="Query Result"):
    """Convert a Pandas DataFrame from Wherobots into a QGIS memory vector layer.

    :param df: Pandas DataFrame returned by cursor.fetchall()
    :param columns: optional list of column names (uses df.columns if None)
    :param layer_name: name for the resulting layer
    :returns: QgsVectorLayer (memory provider)
    """
    import pandas as pd

    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        cols = columns or (list(df.columns) if df is not None else [])
        layer = QgsVectorLayer("Point?crs=EPSG:4326", layer_name, "memory")
        provider = layer.dataProvider()
        fields = [QgsField(col, QVariant.String) for col in cols]
        provider.addAttributes(fields)
        layer.updateFields()
        return layer

    col_names = list(df.columns)
    first_row = df.iloc[0].to_dict()
    geom_col = _detect_geometry_column(col_names, first_row)

    # Attribute columns = everything except geometry
    attr_cols = [c for c in col_names if c != geom_col]

    # Build QGIS fields from DataFrame dtypes
    qgs_fields = QgsFields()
    for col in attr_cols:
        qtype = _dtype_to_qvariant(df[col].dtype)
        qgs_fields.append(QgsField(col, qtype))

    # Detect geometry type and CRS
    if geom_col is not None:
        wkb_type = _detect_geom_type_df(df, geom_col)
        type_str = QgsWkbTypes.displayString(wkb_type) if wkb_type != QgsWkbTypes.Unknown else "Point"
        first_geom_val = df[geom_col].iloc[0]
        _, srid = _parse_ewkt(str(first_geom_val))
    else:
        type_str = "None"
        srid = 4326

    uri = f"{type_str}?crs=EPSG:{srid}"
    layer = QgsVectorLayer(uri, layer_name, "memory")
    provider = layer.dataProvider()
    provider.addAttributes(qgs_fields.toList())
    layer.updateFields()

    # Add features row by row
    features = []
    for _, row in df.iterrows():
        feat = QgsFeature(layer.fields())
        attr_values = []
        for col in attr_cols:
            val = row[col]
            # Convert numpy/pandas types to native Python
            if pd.isna(val):
                attr_values.append(None)
            elif hasattr(val, 'item'):
                attr_values.append(val.item())
            else:
                attr_values.append(val)
        feat.setAttributes(attr_values)

        if geom_col is not None and row.get(geom_col) and isinstance(row[geom_col], str):
            geom, _ = _parse_ewkt(row[geom_col])
            if not geom.isNull():
                feat.setGeometry(geom)
        features.append(feat)

    provider.addFeatures(features)
    layer.updateExtents()
    return layer


def geojson_to_layer(file_path, layer_name="Query Result"):
    """Load a GeoJSON file as a QGIS vector layer.

    :param file_path: path to GeoJSON file
    :param layer_name: display name for the layer
    :returns: QgsVectorLayer
    """
    layer = QgsVectorLayer(file_path, layer_name, "ogr")
    return layer


def raster_file_to_layer(file_path, layer_name="Raster Result"):
    """Load a raster file (GeoTIFF, etc.) as a QGIS raster layer.

    :param file_path: path to raster file
    :param layer_name: display name for the layer
    :returns: QgsRasterLayer
    """
    layer = QgsRasterLayer(file_path, layer_name, "gdal")
    return layer


def add_layer_to_project(layer):
    """Add a layer to the current QGIS project."""
    QgsProject.instance().addMapLayer(layer)


def get_map_extent_wkt(iface):
    """Get the current map canvas extent as a WGS84 WKT polygon.

    :param iface: QgisInterface instance
    :returns: WKT polygon string in EPSG:4326
    """
    canvas = iface.mapCanvas()
    extent = canvas.extent()
    canvas_crs = canvas.mapSettings().destinationCrs()

    # Transform to WGS84
    target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    if canvas_crs != target_crs:
        transform = QgsCoordinateTransform(
            canvas_crs, target_crs, QgsProject.instance()
        )
        extent = transform.transformBoundingBox(extent)

    xmin = extent.xMinimum()
    ymin = extent.yMinimum()
    xmax = extent.xMaximum()
    ymax = extent.yMaximum()

    return (
        f"POLYGON(({xmin} {ymin}, {xmax} {ymin}, "
        f"{xmax} {ymax}, {xmin} {ymax}, {xmin} {ymin}))"
    )


def get_map_extent_bounds(iface):
    """Get the current map canvas extent as (xmin, ymin, xmax, ymax) in WGS84."""
    canvas = iface.mapCanvas()
    extent = canvas.extent()
    canvas_crs = canvas.mapSettings().destinationCrs()

    target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    if canvas_crs != target_crs:
        transform = QgsCoordinateTransform(
            canvas_crs, target_crs, QgsProject.instance()
        )
        extent = transform.transformBoundingBox(extent)

    return (
        extent.xMinimum(),
        extent.yMinimum(),
        extent.xMaximum(),
        extent.yMaximum(),
    )


def _qgis_type_to_sql(qtype):
    """Map QVariant field type to a Wherobots/Spark SQL type."""
    mapping = {
        QVariant.Int: "INT",
        QVariant.LongLong: "BIGINT",
        QVariant.Double: "DOUBLE",
        QVariant.String: "STRING",
        QVariant.Bool: "BOOLEAN",
        QVariant.Date: "DATE",
        QVariant.DateTime: "TIMESTAMP",
    }
    return mapping.get(qtype, "STRING")


def _escape_sql_value(value, qtype):
    """Escape a Python value for embedding in a SQL statement."""
    if value is None or (isinstance(value, str) and value == ""):
        return "NULL"
    if qtype in (QVariant.Int, QVariant.LongLong):
        return str(int(value))
    if qtype == QVariant.Double:
        return str(float(value))
    if qtype == QVariant.Bool:
        return "TRUE" if value else "FALSE"
    # String — escape single quotes
    return "'" + str(value).replace("'", "''") + "'"


def layer_to_insert_sql(layer, table_name, batch_size=500):
    """Generate SQL statements to create a table and insert data from a QGIS layer.

    Yields SQL strings: first a CREATE TABLE, then batched INSERT statements.

    :param layer: QgsVectorLayer source layer
    :param table_name: fully qualified target table name
    :param batch_size: number of rows per INSERT statement
    """
    fields = layer.fields()
    geom_type = layer.wkbType()
    has_geom = geom_type != QgsWkbTypes.NoGeometry

    # Build CREATE TABLE
    col_defs = []
    for field in fields:
        sql_type = _qgis_type_to_sql(field.type())
        col_defs.append(f"  {field.name()} {sql_type}")
    if has_geom:
        col_defs.append("  geometry GEOMETRY")

    create_sql = f"CREATE TABLE {table_name} (\n" + ",\n".join(col_defs) + "\n)"
    yield create_sql

    # Build INSERT statements in batches
    features = list(layer.getFeatures())
    for batch_start in range(0, len(features), batch_size):
        batch = features[batch_start : batch_start + batch_size]
        value_rows = []
        for feat in batch:
            values = []
            for i, field in enumerate(fields):
                values.append(_escape_sql_value(feat.attribute(i), field.type()))
            if has_geom and feat.hasGeometry():
                wkt = feat.geometry().asWkt()
                values.append(f"ST_GeomFromWKT('{wkt}')")
            elif has_geom:
                values.append("NULL")
            value_rows.append("(" + ", ".join(values) + ")")

        col_names = [field.name() for field in fields]
        if has_geom:
            col_names.append("geometry")

        insert_sql = (
            f"INSERT INTO {table_name} ({', '.join(col_names)}) VALUES\n"
            + ",\n".join(value_rows)
        )
        yield insert_sql


def export_layer_to_geojson(layer):
    """Export a QGIS vector layer to a temporary GeoJSON file.

    :param layer: QgsVectorLayer
    :returns: path to the temporary GeoJSON file
    """
    tmp_dir = tempfile.mkdtemp(prefix="wherobots_")
    tmp_path = os.path.join(tmp_dir, "upload.geojson")

    exporter = QgsJsonExporter(layer)
    features = []
    for feat in layer.getFeatures():
        features.append(exporter.exportFeature(feat))

    geojson = {
        "type": "FeatureCollection",
        "features": [json.loads(f) for f in features],
    }

    with open(tmp_path, "w") as f:
        json.dump(geojson, f)

    return tmp_path
