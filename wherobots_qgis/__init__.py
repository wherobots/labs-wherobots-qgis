def classFactory(iface):
    """Load the Wherobots plugin.

    :param iface: A QGIS interface instance (QgisInterface).
    :returns: WherobotsPlugin instance.
    """
    from .plugin import WherobotsPlugin
    return WherobotsPlugin(iface)
