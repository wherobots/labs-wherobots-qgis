"""Tests for PluginSettings — covers the WBC-200 persistence fix.

WBC-200: the "Filter by current map extent" (Use Map Bounds) option was not
saved, so it reset every time the plugin was reopened. It must round-trip
through QgsSettings so a fresh PluginSettings instance (a reopened plugin)
sees the previously chosen value.
"""

import importlib

from tests.support import install_qgis_stubs

install_qgis_stubs()
settings_mod = importlib.import_module("wherobots_qgis.utils.settings")
PluginSettings = settings_mod.PluginSettings


# --- Defaults ---------------------------------------------------------------

def test_filter_by_extent_defaults_off():
    assert PluginSettings().get_filter_by_extent() is False


def test_geometry_column_defaults_to_geometry():
    assert PluginSettings().get_geometry_column() == "geometry"


# --- Persistence across "plugin openings" (separate instances) --------------

def test_filter_by_extent_persists_across_instances():
    PluginSettings().set_filter_by_extent(True)
    # A new instance simulates closing and reopening the plugin.
    assert PluginSettings().get_filter_by_extent() is True


def test_filter_by_extent_persists_when_disabled():
    PluginSettings().set_filter_by_extent(True)
    PluginSettings().set_filter_by_extent(False)
    assert PluginSettings().get_filter_by_extent() is False


def test_geometry_column_persists_across_instances():
    PluginSettings().set_geometry_column("geom")
    assert PluginSettings().get_geometry_column() == "geom"


def test_filter_by_extent_returns_real_bool():
    """Guards against QgsSettings returning the string 'true'/'false'."""
    PluginSettings().set_filter_by_extent(True)
    value = PluginSettings().get_filter_by_extent()
    assert isinstance(value, bool)
