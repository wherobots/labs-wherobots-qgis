from qgis.core import QgsSettings

PREFIX = "wherobots"


class PluginSettings:
    """Typed wrapper around QgsSettings for Wherobots plugin configuration."""

    def __init__(self):
        self._s = QgsSettings()

    def _key(self, name):
        return f"{PREFIX}/{name}"

    # --- API Key ---

    def get_api_key(self):
        return self._s.value(self._key("api_key"), "")

    def set_api_key(self, value):
        self._s.setValue(self._key("api_key"), value)

    # --- Region ---

    def get_region(self):
        return self._s.value(self._key("region"), "aws-us-west-2")

    def set_region(self, value):
        self._s.setValue(self._key("region"), value)

    # --- Runtime ---

    def get_runtime(self):
        return self._s.value(self._key("runtime"), "TINY")

    def set_runtime(self, value):
        self._s.setValue(self._key("runtime"), value)

    # --- Default max rows ---

    def get_default_max_rows(self):
        return int(self._s.value(self._key("default_max_rows"), 100))

    def set_default_max_rows(self, value):
        self._s.setValue(self._key("default_max_rows"), int(value))

    # --- Save credentials flag ---

    def get_save_credentials(self):
        return self._s.value(self._key("save_credentials"), False, type=bool)

    def set_save_credentials(self, value):
        self._s.setValue(self._key("save_credentials"), bool(value))

    def clear_api_key(self):
        self._s.remove(self._key("api_key"))
