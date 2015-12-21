# -*- coding: utf-8 -*-

#******************************************************************************
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
#******************************************************************************


import os
import ConfigParser

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from ui.ui_aboutdialogbase import Ui_Dialog

import resources_rc


class AboutDialog(QDialog, Ui_Dialog):
    def __init__(self):
        QDialog.__init__(self)
        self.setupUi(self)

        self.btnHelp = self.buttonBox.button(QDialogButtonBox.Help)

        self.lblLogo.setPixmap(QPixmap(':/icons/qtiles.png'))

        cfg = ConfigParser.SafeConfigParser()
        cfg.read(os.path.join(os.path.dirname(__file__), 'metadata.txt'))
        version = cfg.get('general', 'version')

        self.lblVersion.setText(self.tr('Version: %s') % version)
        doc = QTextDocument()
        doc.setHtml(self.getAboutText())
        self.textBrowser.setDocument(doc)
        self.textBrowser.setOpenExternalLinks(True)

        self.buttonBox.helpRequested.connect(self.openHelp)

    def reject(self):
        QDialog.reject(self)

    def openHelp(self):
        overrideLocale = QSettings().value('locale/overrideFlag', False, type=bool)
        if not overrideLocale:
            localeFullName = QLocale.system().name()
        else:
            localeFullName = QSettings().value('locale/userLocale', '')

        localeShortName = localeFullName[0:2]
        if localeShortName in ['ru', 'uk']:
            QDesktopServices.openUrl(QUrl('http://gis-lab.info/qa/qtiles.html'))
        else:
            QDesktopServices.openUrl(QUrl('http://gis-lab.info/qa/qtiles-eng.html'))

    def getAboutText(self):
        return self.tr('<p>Generate tiles from QGIS project.</p>'
            '<p>Plugin generates raster tiles from QGIS project corresponding '
            'to <a '
            'href="http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames">'
            'Slippy Map</a> '
            'specification. Output tiles can be saved in directory or as zip '
            'archive.</p>'
            '<p><strong>Developers</strong>: '
            '(<a href="http://nextgis.org">NextGIS</a>), portions of code by '
            'Andrew Naplavkov and Giovanni Allegri.</p>'
            '<p><strong>Homepage</strong>: '
            '<a href="https://github.com/nextgis/QTiles">'
            'https://github.com/nextgis/QTiles</a></p>'
            '<p>Please report bugs at '
            '<a href="https://github.com/nextgis/QTiles/issues">'
            'bugtracker</a></p>'
            )
