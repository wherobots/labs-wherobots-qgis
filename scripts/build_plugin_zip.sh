#!/usr/bin/env bash
#
# Build the distributable QGIS plugin zip.
#
# The archive contains the wherobots_qgis/ plugin package (what QGIS installs)
# plus the repository LICENSE, which the QGIS plugin repository requires to be
# present inside the package. macOS/Python packaging junk is excluded. This is
# the single source of truth for packaging — used both locally and by CI
# (WBC-194).
#
# The zip is assembled in a staging directory so the LICENSE can be placed
# inside the plugin folder without keeping a duplicate copy in the repo.
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

# zip is run from the staging dir, so the output path must be absolute.
case "$OUT" in
  /*) ;;
  *) OUT="$ROOT/$OUT" ;;
esac

if [[ ! -d "$PLUGIN_DIR" ]]; then
  echo "error: plugin directory '$PLUGIN_DIR' not found" >&2
  exit 1
fi

if [[ ! -f LICENSE ]]; then
  echo "error: LICENSE not found at repository root" >&2
  exit 1
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cp -R "$PLUGIN_DIR" "$STAGE/$PLUGIN_DIR"
cp LICENSE "$STAGE/$PLUGIN_DIR/LICENSE"

rm -f "$OUT"
(
  cd "$STAGE"
  zip -r "$OUT" "$PLUGIN_DIR" \
    -x "*.DS_Store" \
    -x "*__pycache__*" \
    -x "*.pyc" \
    -x "*.pyo" > /dev/null
)

echo "Built $OUT"
unzip -l "$OUT" | tail -1
