"""Tests for scripts/build_plugin_zip.sh — the distributable plugin package.

The QGIS plugin repository rejects uploads whose package has no LICENSE
("Cannot find LICENSE in the plugin package"). v0.3.1 shipped without one
because LICENSE lives at the repository root and the zip only contained
wherobots_qgis/. These tests pin the shape of the built archive.
"""

import os
import subprocess
import zipfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_SCRIPT = os.path.join(REPO_ROOT, "scripts", "build_plugin_zip.sh")


@pytest.fixture(scope="module")
def built_zip(tmp_path_factory):
    out = tmp_path_factory.mktemp("dist") / "wherobots_qgis-test.zip"
    subprocess.run([BUILD_SCRIPT, str(out)], cwd=REPO_ROOT, check=True)
    with zipfile.ZipFile(out) as zf:
        yield zf.namelist()


def test_license_is_inside_the_plugin_package(built_zip):
    assert "wherobots_qgis/LICENSE" in built_zip


def test_license_content_matches_repo_license(tmp_path):
    out = tmp_path / "wherobots_qgis-test.zip"
    subprocess.run([BUILD_SCRIPT, str(out)], cwd=REPO_ROOT, check=True)
    with zipfile.ZipFile(out) as zf:
        packaged = zf.read("wherobots_qgis/LICENSE")
    with open(os.path.join(REPO_ROOT, "LICENSE"), "rb") as fh:
        assert packaged == fh.read()


def test_metadata_is_present(built_zip):
    assert "wherobots_qgis/metadata.txt" in built_zip


def test_packaging_junk_is_excluded(built_zip):
    assert not [n for n in built_zip if "__pycache__" in n or n.endswith(".pyc")]
    assert not [n for n in built_zip if n.endswith(".DS_Store")]


def test_everything_is_under_the_plugin_dir(built_zip):
    """QGIS installs the archive's top-level folder as the plugin."""
    assert all(n.startswith("wherobots_qgis/") for n in built_zip)
