# -*- coding: utf-8 -*-

# ******************************************************************************
#
# QTiles
# ---------------------------------------------------------
# Generates tiles from QGIS project
#
# Copyright (C) 2012-2014 NextGIS (info@nextgis.org)
#
# This source is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option)
# any later version.
#
# This code is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# A copy of the GNU General Public License is available on the World Wide Web
# at <http://www.gnu.org/licenses/>. You can also obtain it by writing
# to the Free Software Foundation, 51 Franklin Street, Suite 500 Boston,
# MA 02110-1335 USA.
#
# ******************************************************************************


from typing import TYPE_CHECKING

from qgis.core import QgsRuntimeProfiler

from qtiles.core.exceptions import QTilesReloadAfterUpdateWarning
from qtiles.core.settings import QTilesSettings
from qtiles.qtiles_interface import (
    QTilesInterface,
)

if TYPE_CHECKING:
    from qgis.gui import QgisInterface


def classFactory(_iface: "QgisInterface") -> QTilesInterface:
    """Create and return an instance of the QTiles plugin.

    :param _iface: QGIS interface instance passed by QGIS at plugin load.
    :type _iface: QgisInterface
    :returns: An instance of QTilesInterface (plugin or stub).
    :rtype: QTilesInterface
    """
    settings = QTilesSettings()

    try:
        with QgsRuntimeProfiler.profile("Import plugin"):
            from qtiles.qtiles import QTiles

        plugin = QTiles()
        settings.did_last_launch_fail = False

    except Exception as error:
        import copy

        from qgis.PyQt.QtCore import QTimer

        from qtiles.qtiles_plugin_stub import (
            QTilesPluginStub,
        )

        error_copy = copy.deepcopy(error)
        exception = error_copy

        if not settings.did_last_launch_fail:
            # Sometimes after an update that changes the plugin structure,
            # the plugin may fail to load. Restarting QGIS helps.
            exception = QTilesReloadAfterUpdateWarning()
            exception.__cause__ = error_copy

        settings.did_last_launch_fail = True

        plugin = QTilesPluginStub()

        def display_exception() -> None:
            plugin.notifier.display_exception(exception)

        QTimer.singleShot(0, display_exception)

    return plugin
