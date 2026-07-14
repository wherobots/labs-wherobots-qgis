"""Tests for plugin.py — covers the CUS-37 toolbar-button fix.

CUS-37: the plugin registered a toolbar action but shipped no icon.png, so
the button rendered blank/invisible and users perceived "no button". The icon
asset must exist and the action must be wired up (icon, tooltip, checkable,
kept in sync with the dock).
"""

import importlib
import os
import sys
import types

from PIL import Image

from tests.support import FakeSignal, install_qgis_stubs

install_qgis_stubs()

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_DIR = os.path.join(REPO_ROOT, "wherobots_qgis")


# --- Fakes ------------------------------------------------------------------

class FakeToolBar:
    def __init__(self):
        self.object_name = ""
        self.actions = []

    def setObjectName(self, name):
        self.object_name = name

    def addAction(self, action):
        self.actions.append(action)


class FakeDockWidget:
    def __init__(self, iface, parent=None):
        self.iface = iface
        self.visibilityChanged = FakeSignal()
        self._visible = False
        self.deleted = False

    def isVisible(self):
        return self._visible

    def setVisible(self, value):
        self._visible = bool(value)
        self.visibilityChanged.emit(self._visible)

    def show(self):
        self.setVisible(True)

    def hide(self):
        self.setVisible(False)

    def deleteLater(self):
        self.deleted = True


class FakeIface:
    def __init__(self):
        self.toolbar = FakeToolBar()
        self.web_menu_actions = []
        self.docks = []
        self.removed_web_menu = []
        self.removed_toolbar_icons = []
        self.removed_docks = []

    def addToolBar(self, name):
        return self.toolbar

    def mainWindow(self):
        return None

    def addPluginToWebMenu(self, menu, action):
        self.web_menu_actions.append((menu, action))

    def addDockWidget(self, area, dock):
        self.docks.append((area, dock))

    def removePluginWebMenu(self, menu, action):
        self.removed_web_menu.append((menu, action))

    def removeToolBarIcon(self, action):
        self.removed_toolbar_icons.append(action)

    def removeDockWidget(self, dock):
        self.removed_docks.append(dock)


def _install_fake_dock_module():
    """Inject a fake gui.dock_widget so run() doesn't import the real GUI stack."""
    mod = types.ModuleType("wherobots_qgis.gui.dock_widget")
    mod.DockWidget = FakeDockWidget
    sys.modules["wherobots_qgis.gui.dock_widget"] = mod


def _load_plugin():
    install_qgis_stubs()
    _install_fake_dock_module()
    if "wherobots_qgis.plugin" in sys.modules:
        del sys.modules["wherobots_qgis.plugin"]
    return importlib.import_module("wherobots_qgis.plugin")


# --- The regression test that maps directly to CUS-37 -----------------------

def test_icon_asset_exists_and_is_valid():
    """The missing icon was the whole bug: the button was invisible."""
    icon_path = os.path.join(PLUGIN_DIR, "icon.png")
    assert os.path.exists(icon_path), "icon.png must ship with the plugin"
    assert os.path.getsize(icon_path) > 0

    with Image.open(icon_path) as im:
        assert im.format == "PNG"
        assert im.size == (128, 128)
        # Must have visible (non-transparent) pixels, or it's still invisible.
        alpha = im.convert("RGBA").getchannel("A")
        assert alpha.getextrema()[1] > 0


def test_metadata_icon_matches_shipped_file():
    meta = os.path.join(PLUGIN_DIR, "metadata.txt")
    with open(meta) as fh:
        text = fh.read()
    assert "icon=icon.png" in text
    assert os.path.exists(os.path.join(PLUGIN_DIR, "icon.png"))


# --- Action wiring ----------------------------------------------------------

def test_initgui_adds_toolbar_button_with_nonnull_icon():
    plugin_mod = _load_plugin()
    iface = FakeIface()
    plugin = plugin_mod.WherobotsPlugin(iface)
    plugin.initGui()

    assert iface.toolbar.object_name == "WherobotsToolbar"
    assert len(iface.toolbar.actions) == 1
    action = iface.toolbar.actions[0]

    assert action is plugin.action
    assert action.icon is not None and not action.icon.isNull()
    assert action.object_name == "WherobotsAction"
    assert action.checkable is True
    assert action.tool_tip
    assert (plugin.menu, action) in iface.web_menu_actions


def test_run_opens_dock_and_syncs_button_state():
    plugin_mod = _load_plugin()
    iface = FakeIface()
    plugin = plugin_mod.WherobotsPlugin(iface)
    plugin.initGui()

    plugin.run()  # first call creates + shows the dock
    assert plugin.dock_widget is not None
    assert plugin.dock_widget.isVisible() is True
    assert plugin.action.isChecked() is True
    assert len(iface.docks) == 1

    plugin.run()  # second call hides it
    assert plugin.dock_widget.isVisible() is False
    assert plugin.action.isChecked() is False


def test_closing_dock_directly_unchecks_button():
    plugin_mod = _load_plugin()
    iface = FakeIface()
    plugin = plugin_mod.WherobotsPlugin(iface)
    plugin.initGui()
    plugin.run()
    assert plugin.action.isChecked() is True

    # User closes the dock via its own close button -> visibilityChanged(False).
    plugin.dock_widget.hide()
    assert plugin.action.isChecked() is False


def test_unload_removes_button_and_dock():
    plugin_mod = _load_plugin()
    iface = FakeIface()
    plugin = plugin_mod.WherobotsPlugin(iface)
    plugin.initGui()
    plugin.run()
    dock = plugin.dock_widget

    plugin.unload()
    assert iface.removed_web_menu, "web menu action should be removed"
    assert iface.removed_toolbar_icons, "toolbar icon should be removed"
    assert dock in iface.removed_docks
    assert dock.deleted is True
    assert plugin.dock_widget is None
