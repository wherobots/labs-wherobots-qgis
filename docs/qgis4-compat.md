# QGIS 3.x + QGIS 4.0 (Qt5/Qt6) compatibility

QGIS 4.0 ("Norrköping", March 2026) moves from Qt5/PyQt5 to Qt6/PyQt6. This
plugin ships **one codebase that runs on both** QGIS 3.x and QGIS 4.0 — we do
**not** maintain a separate 4.0 fork.

## Why one codebase, not a fork

A long-lived 4.0 branch would mean every fix has to be applied and kept in sync
twice. Because the plugin imports Qt exclusively through the `qgis.PyQt` layer
and the only real API divergences are small and localised, a single
dual-compatible codebase is cheaper and safer to maintain.

## How compatibility is achieved

### 1. Metadata (`wherobots_qgis/metadata.txt`)

```
qgisMinimumVersion=3.22
qgisMaximumVersion=4.99
```

`qgisMaximumVersion=4.99` is what lists the plugin as QGIS 4 compatible. Do
**not** add `supportsQt6` — that flag was removed from QGIS core and is ignored.

### 2. Scoped enums

PyQt6 only allows fully-scoped enum access; PyQt5 ≥ 5.15 (shipped with every
QGIS 3.22+) accepts the scoped form too. So always write the scoped form:

| Qt5-only (breaks on Qt6) | Dual-compatible |
| --- | --- |
| `Qt.RightDockWidgetArea` | `Qt.DockWidgetArea.RightDockWidgetArea` |
| `QLineEdit.Password` | `QLineEdit.EchoMode.Password` |
| `Qt.TextSelectableByMouse` | `Qt.TextInteractionFlag.TextSelectableByMouse` |

### 3. `qt_compat` for the cases a literal can't cover

[`wherobots_qgis/utils/qt_compat.py`](../wherobots_qgis/utils/qt_compat.py)
centralises the two genuine divergences:

- **Field types.** `QVariant.Int`/`QVariant.String`/… were removed in Qt6 in
  favour of `QMetaType.Type.*`. But the `QMetaType`-based `QgsField`
  constructor only exists since QGIS 3.38, while the `QVariant` one is present
  on every Qt5 build. The shim therefore uses `QVariant` on Qt5 (covering all
  of QGIS 3.22–3.x) and `QMetaType` on Qt6 (QGIS 4.0), keyed off whether
  `QVariant.String` still exists. Import `FIELD_INT`, `FIELD_STRING`, etc.
- **QGIS-native enums.** `QgsTask.Flag.CanCancel`, `QgsWkbTypes.Type.Unknown`
  and `QgsWkbTypes.Type.NoGeometry` are exposed via `_member()`, which prefers
  the scoped class and falls back to the flat attribute on older bindings.
  Import `TASK_CAN_CANCEL`, `WKB_UNKNOWN`, `WKB_NO_GEOMETRY`.

**Rule of thumb:** never write `QVariant.<Type>` or a bare `QgsTask.CanCancel`
in plugin code — add a constant to `qt_compat` and import it.

## Testing without QGIS

The suite stubs `qgis`/`PyQt` (see `tests/support.py`) and exercises both
branches of `qt_compat`: `tests/test_qt_compat.py` simulates a Qt6 binding
(a `QVariant` with no `Type` members and a scoped `QgsWkbTypes.Type`) and
asserts the shim switches to `QMetaType` and the scoped enums.

## Verifying against real QGIS 4

Local unit tests can't load real Qt6. Before release, smoke-test the packaged
zip in an actual QGIS 4.0 install (Install from ZIP), and note that the QGIS
plugin repository runs `pyqgis4-checker` on upload, which flags any remaining
Qt5-only patterns. The official `scripts/pyqt5_to_pyqt6/pyqt5_to_pyqt6.py` in
the QGIS repo can also be run in a Qt6-only environment as a cross-check.
