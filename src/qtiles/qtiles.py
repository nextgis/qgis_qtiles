# ******************************************************************************
#
# QTiles
# ---------------------------------------------------------
# Generates tiles from QGIS project
#
# Copyright (C) 2012-2022 NextGIS (info@nextgis.com)
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

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from osgeo import gdal
from qgis.core import Qgis, QgsApplication
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import (
    QT_VERSION_STR,
    QCoreApplication,
    QObject,
    QSysInfo,
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu
from qgis.utils import iface

from qtiles import resources_rc  # noqa: F401
from qtiles.aboutdialog import AboutDialog
from qtiles.core import utils
from qtiles.core.constants import PACKAGE_NAME, PLUGIN_NAME
from qtiles.core.logging import logger
from qtiles.notifier.message_bar_notifier import MessageBarNotifier
from qtiles.qtiles_interface import (
    QTilesInterface,
)
from qtiles.qtilesdialog import QTilesDialog

if TYPE_CHECKING:
    from qtiles.notifier.notifier_interface import (
        NotifierInterface,
    )

assert isinstance(iface, QgisInterface)


class QTiles(QTilesInterface):
    """QGIS Plugin Implementation."""

    __notifier: Optional[MessageBarNotifier]

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """Initialize the plugin instance.

        :param parent: Optional parent QObject.
        :type parent: Optional[QObject]
        """
        super().__init__(parent)
        metadata_file = self.path / "metadata.txt"

        logger.debug("<b>✓ Plugin created</b>")
        logger.debug(f"<b>ⓘ OS:</b> {QSysInfo().prettyProductName()}")
        logger.debug(f"<b>ⓘ Qt version:</b> {QT_VERSION_STR}")
        logger.debug(f"<b>ⓘ QGIS version:</b> {Qgis.version()}")
        logger.debug(f"<b>ⓘ Python version:</b> {sys.version}")
        logger.debug(f"<b>ⓘ GDAL version:</b> {gdal.__version__}")
        logger.debug(f"<b>ⓘ Plugin version:</b> {self.version}")
        logger.debug(
            f"<b>ⓘ Plugin path:</b> {self.path}"
            + (
                f" -> {metadata_file.resolve().parent}"
                if metadata_file.is_symlink()
                else ""
            )
        )

        self.iface = iface
        self.qtiles_dialog = None

        self.__notifier = None

    @property
    def notifier(self) -> "NotifierInterface":
        """Return the notifier for displaying messages to the user.

        :returns: Notifier interface instance.
        :rtype: NotifierInterface
        :raises AssertionError: If notifier is not initialized.
        """
        assert self.__notifier is not None, "Notifier is not initialized"
        return self.__notifier

    def _load(self) -> None:
        """
        Initialize the QTiles plugin GUI.
        """
        self._add_translator(
            self.path / "i18n" / f"{PACKAGE_NAME}_{utils.locale()}.qm",
        )
        self.__notifier = MessageBarNotifier(self)

        self.__action_run = QAction(
            PLUGIN_NAME,
            self.iface.mainWindow(),
        )
        self.__action_run.setIcon(QIcon(":/plugins/qtiles/icons/qtiles.svg"))
        self.__action_run.setWhatsThis(
            QCoreApplication.translate(
                "QTiles", "Generate tiles from current project"
            )
        )
        self.__action_run.triggered.connect(self.run)

        self.iface.registerMainWindowAction(self.__action_run, "Shift+T")

        self.__action_about = QAction(
            QCoreApplication.translate("QTiles", "About QTiles..."),
            self.iface.mainWindow(),
        )
        self.__action_about.setIcon(
            QgsApplication.getThemeIcon("mActionPropertiesWidget.svg")
        )
        self.__action_about.setWhatsThis("About QTiles")
        self.__action_about.triggered.connect(self.about)

        self.__qtiles_menu = QMenu(PLUGIN_NAME)
        self.__qtiles_menu.setIcon(QIcon(":/plugins/qtiles/icons/qtiles.svg"))

        self.__qtiles_menu.addAction(self.__action_run)
        self.__qtiles_menu.addAction(self.__action_about)

        raster_menu = self.iface.rasterMenu()
        assert raster_menu is not None
        raster_menu.addMenu(self.__qtiles_menu)

        self.__qtiles_toolbar = self.iface.addToolBar("QTiles Toolbar")
        assert self.__qtiles_toolbar is not None

        self.__qtiles_toolbar.setObjectName("QTilesToolbar")
        self.__qtiles_toolbar.addAction(self.__action_run)
        self.__qtiles_toolbar.setToolTip(
            QCoreApplication.translate("QTiles", "QTiles Toolbar")
        )

        self.__show_help_action = QAction(
            QIcon(":/plugins/qtiles/icons/qtiles.svg"),
            PLUGIN_NAME,
        )
        self.__show_help_action.triggered.connect(self.about)
        self.__plugin_help_menu = self.iface.pluginHelpMenu()
        assert self.__plugin_help_menu is not None
        self.__plugin_help_menu.addAction(self.__show_help_action)

    def _unload(self) -> None:
        """
        Unload the QTiles plugin interface.
        """
        self.iface.unregisterMainWindowAction(self.__action_run)

        raster_menu = self.iface.rasterMenu()
        assert raster_menu is not None

        if self.__qtiles_menu is not None:
            raster_menu.removeAction(self.__qtiles_menu.menuAction())
            self.__qtiles_menu.deleteLater()
            self.__qtiles_menu = None

        assert self.__qtiles_toolbar is not None
        self.__qtiles_toolbar.hide()
        self.__qtiles_toolbar.deleteLater()

        self.__action_run.deleteLater()

        self.__action_about.deleteLater()

        if self.__plugin_help_menu:
            self.__plugin_help_menu.removeAction(self.__show_help_action)
        self.__show_help_action.deleteLater()
        self.__show_help_action = None

        if self.__notifier is not None:
            self.__notifier.deleteLater()
            self.__notifier = None

    def run(self) -> None:
        """
        Show the main QTiles dialog.

        Ensures that only a single non-modal instance of the dialog exists.

        :return: None
        """
        if self.qtiles_dialog is None:
            self.qtiles_dialog = QTilesDialog(self.iface)
            self.qtiles_dialog.finished.connect(
                lambda _: setattr(self, "qtiles_dialog", None)
            )
            self.qtiles_dialog.show()
        else:
            self.qtiles_dialog.raise_()
            self.qtiles_dialog.activateWindow()

    def about(self):
        package_name = str(Path(__file__).parent.name)
        d = AboutDialog(package_name)
        d.exec()
