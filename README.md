# Wherobots for QGIS

Connect to [Wherobots Cloud](https://wherobots.com) from QGIS for spatial SQL
queries, data upload, and raster operations. Execute spatial SQL and view
results as map layers, upload local layers to Wherobots tables, and query
raster data directly into your map canvas.

## Wherobots Labs

This is a [Wherobots Labs](https://wherobots.com/labs) project.

> Wherobots Labs projects were developed for customers to use. However test coverage is limited, and you are responsible for ensuring the project is ready for your use case. Wherobots does not make any guarantees about production readiness but you are free to adopt the software, contribute to its success, and fork the projects.

> Any issues discovered through the use of this project should be filed as issues on the GitHub Repo. They will be reviewed as time permits, but there are no formal SLAs for support.

Please file bugs and feature requests through
[GitHub Issues](https://github.com/wherobots/labs-wherobots_qgis/issues).
See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how to contribute.

## Requirements

- QGIS 3.22 or newer
- A Wherobots Cloud API key
- The [`wherobots-python-dbapi`](https://pypi.org/project/wherobots-python-dbapi/)
  package installed **into QGIS's bundled Python** (see below)

## Installing the plugin

Download `wherobots_qgis-<version>.zip` from the repository's
[**Releases**](https://github.com/wherobots/wherobots_qgis/releases) page, then
in QGIS go to **Plugins → Manage and Install Plugins → Install from ZIP** and
select the downloaded file. The zip is built automatically by CI — you don't
need to package it yourself.

(For an unreleased/in-development build, download the `wherobots_qgis-*` artifact
from the latest run of the **Build plugin zip** GitHub Actions workflow.)

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

### Building and releasing the zip

The distributable zip is a build artifact, not a checked-in file. Build it
locally with:

```bash
scripts/build_plugin_zip.sh            # -> wherobots_qgis.zip
```

CI (`.github/workflows/build-plugin-zip.yml`) runs the tests and builds the zip
on every push and pull request, uploading it as a workflow artifact. To publish
a **GitHub Release** with the zip attached, bump `version=` in
`wherobots_qgis/metadata.txt` and push a matching tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```
