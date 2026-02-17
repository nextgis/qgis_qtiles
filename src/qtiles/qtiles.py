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


from pathlib import Path

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import (
    QCoreApplication,
    QLocale,
    QSettings,
    QTranslator,
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu

from qtiles import resources_rc  # noqa: F401
from qtiles.aboutdialog import AboutDialog
from qtiles.qtilesdialog import QTilesDialog


class QTilesPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.qtiles_dialog = None

        self.plugin_dir = Path(__file__).parent

        override_locale = QSettings().value(
            "locale/overrideFlag", False, type=bool
        )

        if override_locale:
            locale = QSettings().value("locale/userLocale", "")
        else:
            locale = QLocale.system().name()

        qm_path = self.plugin_dir / "i18n" / f"qtiles_{locale}.qm"

        if qm_path.exists():
            self.translator = QTranslator()
            self.translator.load(str(qm_path))
            QCoreApplication.installTranslator(self.translator)

    def initGui(self):
        self.__action_run = QAction(
            QCoreApplication.translate("QTiles", "QTiles"),
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

        self.__qtiles_menu = QMenu(
            QCoreApplication.translate("QTiles", "QTiles")
        )
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
            "QTiles",
        )
        self.__show_help_action.triggered.connect(self.about)
        self.__plugin_help_menu = self.iface.pluginHelpMenu()
        assert self.__plugin_help_menu is not None
        self.__plugin_help_menu.addAction(self.__show_help_action)

    def unload(self):
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
