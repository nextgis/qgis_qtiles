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


import math
import time
from string import Template

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from qgis.core import *

from tile import Tile
from writers import *

import resources_rc


class TilingThread(QThread):

    rangeChanged = pyqtSignal(str, int)
    updateProgress = pyqtSignal()
    processFinished = pyqtSignal()
    processInterrupted = pyqtSignal()

    def __init__(self, layers, extent, minZoom, maxZoom, width, height, transp,
                 suffix, outputPath, rootDir, antialiasing, tmsConvention,
                 mapUrl, viewer):
        QThread.__init__(self, QThread.currentThread())
        self.mutex = QMutex()
        self.stopMe = 0
        self.interrupted = False

        self.layers = layers
        self.extent = extent
        self.minZoom = minZoom
        self.maxZoom = maxZoom
        self.output = outputPath
        self.width = width
        if rootDir:
            self.rootDir = rootDir
        else:
            self.rootDir = 'tileset_%s' % unicode(time.time()).split('.')[0]

        self.antialias = antialiasing
        self.tmsConvention = tmsConvention

        self.suffix = suffix
        self.mapurl = mapUrl
        self.viewer = viewer

        if self.output.isDir():
            self.mode = 'DIR'
        elif self.output.suffix().lower() == "zip":
            self.mode = 'ZIP'
        elif self.output.suffix().lower() == 'mbtiles':
            self.mode = 'MBTILES'
            self.tmsConvention = True

        self.interrupted = False
        self.tiles = []

        myRed = QgsProject.instance().readNumEntry(
                'Gui', '/CanvasColorRedPart', 255)[0]
        myGreen = QgsProject.instance().readNumEntry(
                'Gui', '/CanvasColorGreenPart', 255)[0]
        myBlue = QgsProject.instance().readNumEntry(
                'Gui', '/CanvasColorBluePart', 255)[0]

        if int(QT_VERSION_STR[2]) >= 8:
            self.color = QColor(myRed, myGreen, myBlue, transp)
        else:
            self.color = qRgb(myRed, myGreen, myBlue, transp)

        self.image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)

        self.projector = QgsCoordinateTransform(
                QgsCoordinateReferenceSystem('EPSG:4326'),
                QgsCoordinateReferenceSystem('EPSG:3395'))

        self.scaleCalc = QgsScaleCalculator()
        self.scaleCalc.setDpi(self.image.logicalDpiX())
        self.scaleCalc.setMapUnits(
                QgsCoordinateReferenceSystem('EPSG:3395').mapUnits())

        self.labeling = QgsPalLabeling()
        self.renderer = QgsMapRenderer()
        self.renderer.setOutputSize(
                self.image.size(), self.image.logicalDpiX())
        self.renderer.setDestinationCrs(
                QgsCoordinateReferenceSystem('EPSG:3395'))
        self.renderer.setProjectionsEnabled(True)
        self.renderer.setLabelingEngine(self.labeling)
        self.renderer.setLayerSet(self.layers)

    def run(self):
        self.mutex.lock()
        self.stopMe = 0
        self.mutex.unlock()

        # prepare output
        if self.mode == 'DIR':
            self.writer = DirectoryWriter(self.output, self.rootDir)
            if self.mapurl:
                self.writeMapurlFile()

            if self.viewer:
                self.writeLeafletViewer()
        elif self.mode == 'ZIP':
            self.writer = ZipWriter(self.output, self.rootDir)
        elif self.mode == 'MBTILES':
            self.writer = MBTilesWriter(self.output, self.rootDir)

        self.rangeChanged.emit(self.tr('Searching tiles...'), 0)

        useTMS = 1
        if self.tmsConvention:
            useTMS = -1

        self.countTiles(Tile(0, 0, 0, useTMS))

        if self.interrupted:
            #del self.tiles[:]
            #self.tiles = None

            self.processInterrupted.emit()

        self.rangeChanged.emit(
                self.tr('Rendering: %v from %m (%p%)'), len(self.tiles))

        self.painter = QPainter()
        if self.antialias:
            self.painter.setRenderHint(QPainter.Antialiasing)

        for t in self.tiles:
            self.render(t)

            self.updateProgress.emit()

            self.mutex.lock()
            s = self.stopMe
            self.mutex.unlock()
            if s == 1:
                self.interrupted = True
                break

        self.writer.finalize()

        if not self.interrupted:
            self.processFinished.emit()
        else:
            self.processInterrupted.emit()

    def stop(self):
        self.mutex.lock()
        self.stopMe = 1
        self.mutex.unlock()

        QThread.wait(self)

    def writeMapurlFile(self):
        filePath = '%s/%s.mapurl' % (
                self.output.absoluteFilePath(), self.rootDir)
        tileServer = 'tms' if self.tmsConvention else 'google'
        with open(filePath, 'w') as mapurl:
            mapurl.write('%s=%s\n' %
                         ('url', self.rootDir + '/ZZZ/XXX/YYY.png'))
            mapurl.write('%s=%s\n' % ('minzoom', self.minZoom))
            mapurl.write('%s=%s\n' % ('maxzoom', self.maxZoom))
            mapurl.write('%s=%f %f\n' % (
                    'center', self.extent.center().x(),
                    self.extent.center().y()))
            mapurl.write('%s=%s\n' % ('type', tileServer))

    def writeLeafletViewer(self):
        templateFile = QFile(':/resources/viewer.html')
        if templateFile.open(QIODevice.ReadOnly | QIODevice.Text):
            viewer = MyTemplate(unicode(templateFile.readAll()))
            tilesDir = '%s/%s' % (self.output.absoluteFilePath(), self.rootDir)
            useTMS = 'true' if self.tmsConvention else 'false'
            substitutions = {'tilesdir'    : tilesDir,
                             'tilesetname' : self.rootDir,
                             'tms'         : useTMS,
                             'centerx'     : self.extent.center().x(),
                             'centery'     : self.extent.center().y(),
                             'avgzoom'     : (self.maxZoom + self.minZoom) / 2,
                             'maxzoom'     : self.maxZoom
                            }

            filePath = '%s/%s.html' % (
                    self.output.absoluteFilePath(), self.rootDir)
            with open(filePath, 'w') as fOut:
                fOut.write(viewer.substitute(substitutions))

            templateFile.close()

    def countTiles(self, tile):
        if self.interrupted or not self.extent.intersects(tile.toRectangle()):
            return

        if self.minZoom <= tile.z and tile.z <= self.maxZoom:
            self.tiles.append(tile)

        if tile.z < self.maxZoom:
            for x in xrange(2 * tile.x, 2 * tile.x + 2, 1):
                for y in xrange(2 * tile.y, 2 * tile.y + 2, 1):
                    self.mutex.lock()
                    s = self.stopMe
                    self.mutex.unlock()
                    if s == 1:
                        self.interrupted = True
                        return

                    subTile = Tile(x, y, tile.z + 1, tile.tms)
                    self.countTiles(subTile)

    def render(self, tile):
        self.renderer.setExtent(self.projector.transform(tile.toRectangle()))
        scale = self.scaleCalc.calculate(self.renderer.extent(), self.width)
        self.renderer.setScale(scale)
        self.image.fill(self.color)
        self.painter.begin(self.image)
        self.renderer.render(self.painter)
        self.painter.end()

        # save image
        self.writer.writeTile(tile, self.image, self.suffix)


class MyTemplate(Template):
    delimiter = '@'

    def __init__(self, templateString):
        Template.__init__(self, templateString)
