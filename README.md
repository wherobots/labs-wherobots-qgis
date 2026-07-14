# Wherobots for QGIS

Connect to [Wherobots Cloud](https://wherobots.com) from QGIS for spatial SQL
queries, data upload, and raster operations. Execute spatial SQL and view
results as map layers, upload local layers to Wherobots tables, and query
raster data directly into your map canvas.

## Requirements

- QGIS 3.22 or newer
- A Wherobots Cloud API key
- The [`wherobots-python-dbapi`](https://pypi.org/project/wherobots-python-dbapi/)
  package installed **into QGIS's bundled Python** (see below)

## Installing the `wherobots-python-dbapi` dependency

The plugin talks to Wherobots through the `wherobots-python-dbapi` package,
which must be available to the Python interpreter that QGIS runs — not your
system or `pyenv`/Homebrew Python.

**Recommended (all platforms).** Open the QGIS Python Console
(**Plugins → Python Console**) and run:

```python
import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "wherobots-python-dbapi"])
```

Then restart QGIS.

`sys.executable` always resolves to the interpreter QGIS is actually running,
so this works regardless of where QGIS is installed. Prefer it over hardcoded
paths: on macOS in particular there is **no** `python3` at
`/Applications/QGIS.app/Contents/MacOS/bin/python3` on many installs, so the
literal path from older docs fails with `no such file or directory`.

### Installing from a terminal instead

If you would rather use a terminal, locate the QGIS interpreter first — do not
assume the path. From the QGIS Python Console:

```python
import sys; print(sys.executable)
```

Then run pip against exactly that path, for example:

```bash
"<paste the path printed above>" -m pip install "wherobots-python-dbapi"
```

If the plugin loads but connecting fails with a message about the missing
package, that means the dependency landed in a different Python than the one
QGIS is running — repeat the steps above from the QGIS Python Console.

## Usage

1. Open the Wherobots panel from the toolbar or **Web → Wherobots**.
2. Enter your API key, pick a region and runtime, and click **Connect**
   (the runtime may take up to a minute to start).
3. Use the **SQL Query**, **Upload**, and **Raster** tabs once connected.

## Development

The plugin's pure-Python logic layers are unit-tested outside QGIS — the test
suite stubs the `qgis`/`PyQt` runtime, so no QGIS install is required.

```bash
pip install -r requirements-dev.txt
pytest
```

Tests that require the `wherobots-python-dbapi` package skip automatically when
it is not installed.
