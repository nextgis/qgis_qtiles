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


from qgis.core import *
from qgis.PyQt.QtCore import (
    QCoreApplication,
    QFileInfo,
    QLocale,
    QSettings,
    QTranslator,
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu, QMessageBox
from pathlib import Path

from . import aboutdialog, qtilesdialog, resources_rc  # noqa: F401
from .compat import QGis, qgisUserDatabaseFilePath


class QTilesPlugin:
    def __init__(self, iface):
        self.iface = iface

        self.qgsVersion = str(QGis.QGIS_VERSION_INT)

        userPluginPath = (
            QFileInfo(qgisUserDatabaseFilePath()).path()
            + "/python/plugins/qtiles"
        )
        systemPluginPath = (
            QgsApplication.prefixPath() + "/python/plugins/qtiles"
        )

        overrideLocale = QSettings().value(
            "locale/overrideFlag", False, type=bool
        )
        if not overrideLocale:
            localeFullName = QLocale.system().name()
        else:
            localeFullName = QSettings().value("locale/userLocale", "")

        if QFileInfo(userPluginPath).exists():
            translationPath = (
                userPluginPath + "/i18n/qtiles_" + localeFullName + ".qm"
            )
        else:
            translationPath = (
                systemPluginPath + "/i18n/qtiles_" + localeFullName + ".qm"
            )

        self.localePath = translationPath
        if QFileInfo(self.localePath).exists():
            self.translator = QTranslator()
            self.translator.load(self.localePath)
            QCoreApplication.installTranslator(self.translator)

    def initGui(self):
        if int(self.qgsVersion) < 20000:
            qgisVersion = (
                self.qgsVersion[0]
                + "."
                + self.qgsVersion[2]
                + "."
                + self.qgsVersion[3]
            )
            QMessageBox.warning(
                self.iface.mainWindow(),
                QCoreApplication.translate("QTiles", "Error"),
                QCoreApplication.translate("QTiles", "QGIS %s detected.\n")
                % qgisVersion
                + QCoreApplication.translate(
                    "QTiles",
                    "This version of QTiles requires at least QGIS 2.0. Plugin will not be enabled.",
                ),
            )
            return None

        self.actionRun = QAction(
            QCoreApplication.translate("QTiles", "QTiles"),
            self.iface.mainWindow(),
        )
        self.iface.registerMainWindowAction(self.actionRun, "Shift+T")
        self.actionRun.setIcon(QIcon(":/plugins/qtiles/icons/qtiles.png"))
        self.actionRun.setWhatsThis("Generate tiles from current project")
        self.actionAbout = QAction(
            QCoreApplication.translate("QTiles", "About QTiles..."),
            self.iface.mainWindow(),
        )
        self.actionAbout.setIcon(QIcon(":/plugins/qtiles/icons/about.png"))
        self.actionAbout.setWhatsThis("About QTiles")

        self.__qtiles_menu = QMenu(
            QCoreApplication.translate("QTiles", "QTiles")
        )
        self.__qtiles_menu.setIcon(QIcon(":/plugins/qtiles/icons/qtiles.png"))

        self.__qtiles_menu.addAction(self.actionRun)
        self.__qtiles_menu.addAction(self.actionAbout)

        self.iface.pluginMenu().addMenu(self.__qtiles_menu)

        self.iface.addToolBarIcon(self.actionRun)

        self.actionRun.triggered.connect(self.run)
        self.actionAbout.triggered.connect(self.about)

        self.__show_help_action = QAction(
            QIcon(":/plugins/qtiles/icons/qtiles.png"),
            "QTiles",
        )
        self.__show_help_action.triggered.connect(self.about)
        self.__plugin_help_menu = self.iface.pluginHelpMenu()
        assert self.__plugin_help_menu is not None
        self.__plugin_help_menu.addAction(self.__show_help_action)

    def unload(self):
        self.iface.unregisterMainWindowAction(self.actionRun)

        self.iface.removeToolBarIcon(self.actionRun)
        self.iface.removePluginMenu(
            QCoreApplication.translate("QTiles", "QTiles"), self.actionRun
        )
        self.iface.removePluginMenu(
            QCoreApplication.translate("QTiles", "QTiles"), self.actionAbout
        )
        self.__qtiles_menu.deleteLater()

        if self.__plugin_help_menu:
            self.__plugin_help_menu.removeAction(self.__show_help_action)
        self.__show_help_action.deleteLater()
        self.__show_help_action = None

    def run(self):
        d = qtilesdialog.QTilesDialog(self.iface)
        d.show()
        d.exec()

    def about(self):
        package_name = str(Path(__file__).parent.name)
        d = aboutdialog.AboutDialog(package_name)
        d.exec()
