#!/usr/bin/env bash
#
# Build the distributable QGIS plugin zip.
#
# The archive contains only the wherobots_qgis/ plugin package (what QGIS
# installs), with macOS/Python packaging junk excluded. This is the single
# source of truth for packaging — used both locally and by CI (WBC-194).
#
# Usage:
#   scripts/build_plugin_zip.sh [output_path]
#
# Defaults to ./wherobots_qgis.zip when no output path is given.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="${1:-wherobots_qgis.zip}"
PLUGIN_DIR="wherobots_qgis"

if [[ ! -d "$PLUGIN_DIR" ]]; then
  echo "error: plugin directory '$PLUGIN_DIR' not found" >&2
  exit 1
fi

rm -f "$OUT"
zip -r "$OUT" "$PLUGIN_DIR" \
  -x "*.DS_Store" \
  -x "*__pycache__*" \
  -x "*.pyc" \
  -x "*.pyo" > /dev/null

echo "Built $OUT"
unzip -l "$OUT" | tail -1
