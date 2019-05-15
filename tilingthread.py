# -*- coding: utf-8 -*-

#******************************************************************************
#
# QTiles
# ---------------------------------------------------------
# Generates tiles from QGIS project
#
# Copyright (C) 2012-2014 NextGIS (info@nextgis.org)
# Copyright (C) 2019 Alexander Bruy (alexander.bruy@gmail.com)
# Copyright (C) 2019 Nacho Urenda (nurenda@gmail.com)
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
import codecs
import json
from string import Template
import time
import datetime

import sys
import os

from qgis.PyQt.QtCore import QCoreApplication, QThread, pyqtSignal, QMutex, Qt, QFile, QIODevice, QRect, QSize
from qgis.PyQt.QtGui import QColor, QImage, QPainter, QBrush
from qgis.core import QgsProject, QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsMapRendererCustomPainterJob, QgsScaleCalculator, QgsMapSettings, QgsRectangle

from . import resources_rc
from .tile import Tile, TileLevelInfo, tileFromLatLon
from .writers import DirectoryWriter, ZipWriter, NGMArchiveWriter, MBTilesWriter

# sys.path.append("C:\Python37\Lib\site-packages")
# import pydevd

class TilingThread(QThread):
    rangeChanged = pyqtSignal(str, int)
    updateProgress = pyqtSignal(int, int)
    processFinished = pyqtSignal()
    processInterrupted = pyqtSignal()
    threshold = pyqtSignal(int)

    warning_threshold_tiles_count = 10000
    
    def __init__(self, layers, extent, minZoom, maxZoom, width, height, macroTileSize, 
                 transp, quality, fileFormat, outputPath, rootDir, antialiasing, tmsConvention, 
                 mbtilesCompression, jsonFile, overview, skipBlankTiles, mapUrl, viewer):
        QThread.__init__(self, QThread.currentThread())

        self.mutex = QMutex()
        self.confirmMutex = QMutex()
        self.tileLevelInfoList = []
        self.stopMe = 0
        self.interrupted = False
        self.tile_count = 0
        self.blank_count = 0
        self.numTiles = 0
        self.layers = layers
        self.extent = extent
        self.minZoom = minZoom
        self.maxZoom = maxZoom
        self.output = outputPath
        self.width = width
        self.height = height
        self.macroTileSize = macroTileSize
        self.transp = transp
        if rootDir:
            self.rootDir = rootDir
        else:
            self.rootDir = 'tileset_%s' % str(time.time()).split('.')[0]
        self.antialias = antialiasing
        self.tmsConvention = tmsConvention
        self.mbtilesCompression = mbtilesCompression
        self.fileFormat = fileFormat
        self.quality = quality
        self.jsonFile = jsonFile
        self.overview = overview
        self.skipBlankTiles = skipBlankTiles
        self.mapurl = mapUrl
        self.viewer = viewer
        if self.output.isDir():
            self.mode = 'DIR'
        elif self.output.suffix().lower() == "zip":
            self.mode = 'ZIP'
        elif self.output.suffix().lower() == "ngrc":
            self.mode = 'NGM'
        elif self.output.suffix().lower() == 'mbtiles':
            self.mode = 'MBTILES'
            self.tmsConvention = True
        self.interrupted = False
        self.layersId = []
        for layer in self.layers:
            self.layersId.append(layer.id())
        myRed = QgsProject.instance().readNumEntry('Gui', '/CanvasColorRedPart', 255)[0]
        myGreen = QgsProject.instance().readNumEntry('Gui', '/CanvasColorGreenPart', 255)[0]
        myBlue = QgsProject.instance().readNumEntry('Gui', '/CanvasColorBluePart', 255)[0]
        self.color = QColor(myRed, myGreen, myBlue, self.transp)
        
        h = (self.height*self.macroTileSize) + (self.height*2)
        w = self.width + (self.width*2)
        image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        
        self.projector = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), QgsCoordinateReferenceSystem('EPSG:3857'), QgsProject.instance())
        self.scaleCalc = QgsScaleCalculator()
        self.scaleCalc.setDpi(image.logicalDpiX())
        self.scaleCalc.setMapUnits(QgsCoordinateReferenceSystem('EPSG:3857').mapUnits())
        self.settings = QgsMapSettings()
        self.settings.setBackgroundColor(self.color)
        self.settings.setOutputDpi(image.logicalDpiX())
        self.settings.setOutputImageFormat(QImage.Format_ARGB32_Premultiplied)
        self.settings.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
        self.settings.setOutputSize(image.size())
        self.settings.setLayers(self.layers)
        if self.antialias:
            self.settings.setFlag(QgsMapSettings.Antialiasing, True)
        else:
            self.settings.setFlag(QgsMapSettings.DrawLabeling, True)

    def run(self):
        self.mutex.lock()
        self.stopMe = 0
        self.mutex.unlock()
        if self.mode == 'DIR':
            self.writer = DirectoryWriter(self.output, self.rootDir)
            if self.mapurl:
                self.writeMapurlFile()
            if self.viewer:
                self.writeLeafletViewer()
        elif self.mode == 'ZIP':
            self.writer = ZipWriter(self.output, self.rootDir)
        elif self.mode == 'NGM':
            self.writer = NGMArchiveWriter(self.output, self.rootDir)
        elif self.mode == 'MBTILES':
            self.writer = MBTilesWriter(self.output, self.rootDir, self.fileFormat, self.minZoom, self.maxZoom, self.extent, self.mbtilesCompression)
        if self.jsonFile:
            self.writeJsonFile()
        if self.overview:
            self.writeOverviewFile()

        self.numTiles = self.calculateTileSets()

        self.rangeChanged.emit(self.tr('Rendering: %v from %m (%p%)'), self.numTiles)

        if self.numTiles > self.warning_threshold_tiles_count:
            self.confirmMutex.lock()
            self.threshold.emit(self.warning_threshold_tiles_count)

        self.confirmMutex.lock()
        if self.interrupted:
            self.processInterrupted.emit()
            return

        self.renderMacroTiles()

        self.writer.finalize()

        self.mutex.lock()
        if not self.interrupted:
            self.processFinished.emit()
            self.mutex.unlock()
            return
        else:
            self.processInterrupted.emit()
            self.mutex.unlock()
            return

    def stop(self):
        self.mutex.lock()
        self.stopMe = 1
        self.mutex.unlock()
        QThread.wait(self)

    def confirmContinue(self):
        self.confirmMutex.unlock()

    def confirmStop(self):
        self.interrupted = True
        self.confirmMutex.unlock()

    def writeJsonFile(self):
        filePath = '%s.json' % self.output.absoluteFilePath()
        if self.mode == 'DIR':
            filePath = '%s/%s.json' % (self.output.absoluteFilePath(), self.rootDir)
        info = {
            'name': self.rootDir,
            'format': self.fileFormat.lower(),
            'minZoom': self.minZoom,
            'maxZoom': self.maxZoom,
            'bounds': str(self.extent.xMinimum()) + ',' + str(self.extent.yMinimum()) + ',' + str(self.extent.xMaximum()) + ','+ str(self.extent.yMaximum())
        }
        with open(filePath, 'w') as f:
            f.write( json.dumps(info) )

    def writeOverviewFile(self):
#        image = QImage(self.settings.outputSize(), QImage.Format_ARGB32)
        image = QImage(QSize(self.width, self.height), QImage.Format_ARGB32)
        image.fill(Qt.transparent)

        dpm = self.settings.outputDpi() / 25.4 * 1000
        image.setDotsPerMeterX(dpm)
        image.setDotsPerMeterY(dpm)

        self.settings.setBackgroundColor(self.color)
        self.settings.setOutputDpi(image.logicalDpiX())
        self.settings.setOutputImageFormat(QImage.Format_ARGB32_Premultiplied)
        self.settings.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
        self.settings.setOutputSize(image.size())
        self.settings.setLayers(self.layers)
        if self.antialias:
            self.settings.setFlag(QgsMapSettings.Antialiasing, True)
        else:
            self.settings.setFlag(QgsMapSettings.DrawLabeling, True)

        self.settings.setExtent(self.projector.transform(self.extent))

        painter = QPainter(image)
        job = QgsMapRendererCustomPainterJob(self.settings, painter)
        job.renderSynchronously()
        # This increases plugin stability with very little impact on performance
        QCoreApplication.processEvents()
        # QCoreApplication.sendPostedEvents()
        painter.end()

        filePath = '%s.%s' % (self.output.absoluteFilePath(), self.fileFormat.lower())
        if self.mode == 'DIR':
            filePath = '%s/%s.%s' % (self.output.absoluteFilePath(), self.rootDir, self.fileFormat.lower())
        image.save(filePath, self.fileFormat, self.quality)

        h = (self.height*self.macroTileSize) + (self.height*2)
        w = self.width + (self.width*2)
        image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        self.settings.setBackgroundColor(self.color)
        self.settings.setOutputDpi(image.logicalDpiX())
        self.settings.setOutputImageFormat(QImage.Format_ARGB32_Premultiplied)
        self.settings.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
        self.settings.setOutputSize(image.size())
        self.settings.setLayers(self.layers)
        if self.antialias:
            self.settings.setFlag(QgsMapSettings.Antialiasing, True)
        else:
            self.settings.setFlag(QgsMapSettings.DrawLabeling, True)


    def writeMapurlFile(self):
        filePath = '%s/%s.mapurl' % (self.output.absoluteFilePath(), self.rootDir)
        tileServer = 'tms' if self.tmsConvention else 'google'
        with open(filePath, 'w') as mapurl:
            mapurl.write('%s=%s\n' % ('url', self.rootDir + '/ZZZ/XXX/YYY.png'))
            mapurl.write('%s=%s\n' % ('minzoom', self.minZoom))
            mapurl.write('%s=%s\n' % ('maxzoom', self.maxZoom))
            mapurl.write('%s=%f %f\n' % ('center', self.extent.center().x(), self.extent.center().y()))
            mapurl.write('%s=%s\n' % ('type', tileServer))

    def writeLeafletViewer(self):
        templateFile = QFile(':/resources/viewer.html')
        if templateFile.open(QIODevice.ReadOnly | QIODevice.Text):
            viewer = MyTemplate(str(templateFile.readAll(), 'utf-8'))

            tilesDir = '%s/%s' % (self.output.absoluteFilePath(), self.rootDir)
            useTMS = 'true' if self.tmsConvention else 'false'
            substitutions = {
                'tilesdir': tilesDir,
                'tilesext': self.fileFormat.lower(),
                'tilesetname': self.rootDir,
                'tms': useTMS,
                'centerx': self.extent.center().x(),
                'centery': self.extent.center().y(),
                'avgzoom': (self.maxZoom + self.minZoom) / 2,
                'maxzoom': self.maxZoom
            }

            filePath = '%s/%s.html' % (self.output.absoluteFilePath(), self.rootDir)
            with codecs.open(filePath, 'w', 'utf-8') as fOut:
                fOut.write(viewer.substitute(substitutions))
            templateFile.close()

    def calculateTileSets(self):
        totalTiles = 0
        self.tileLevelInfoList.clear()
        
        lat_min = self.extent.yMinimum()
        lon_min = self.extent.xMinimum()
        lat_max = self.extent.yMaximum()
        lon_max = self.extent.xMaximum()
        
        for zoom in range(self.minZoom, self.maxZoom+1):
            tileMin = tileFromLatLon(lat_min, lon_min, zoom)
            tileMax = tileFromLatLon(lat_max, lon_max, zoom)
            
            self.tileLevelInfoList.append(TileLevelInfo(zoom, tileMin.x, tileMin.y, tileMax.x, tileMax.y))
            
            ncols = (tileMax.x - tileMin.x) + 1
            nrows = abs(tileMax.y - tileMin.y) + 1
            levelTiles = ncols * nrows
            totalTiles += levelTiles
            
        return totalTiles
            
    def renderMacroTiles(self):
        try:
            # trace("Start: %s" % datetime.datetime.now())
            if self.skipBlankTiles:
                # Prepare a blank image to compare
                # Initialize a temporal image
                tmpImage = QImage(self.settings.outputSize(), QImage.Format_ARGB32)
                tmpImage.fill(Qt.transparent)
                # set parameters coomon to tile images
                dpm = self.settings.outputDpi() / 25.4 * 1000
                tmpImage.setDotsPerMeterX(dpm)
                tmpImage.setDotsPerMeterY(dpm)
                # Draw image background whit the canvas color
                p = QPainter(tmpImage)
                p.fillRect(QRect(0, 0, self.width, self.height), QBrush(self.color))
                # return blank image
                blank_image = tmpImage.copy(0, 0, self.width, self.height) 
            
            # zoom level loop
            for tli in self.tileLevelInfoList:
                # establish parameters common to all zoom levels
                # tms = False
                z = tli.zoomLevel
                dpm = self.settings.outputDpi() / 25.4 * 1000
    
                # column loop
                x = tli.firstCol
    
                while x <= tli.lastCol:
                    #row loop
                    y = min(tli.firstRow, tli.lastRow)
                    ymax = max(tli.firstRow, tli.lastRow)
                    
                    while y <= ymax:
                        # Calculate drawing window
                        xini = x - 1
                        yini = y - 1
                        xfin = x + 1 + 1
                        yfin = y + self.macroTileSize + 1
                        
    #                     iniPoint = Tile(xini, yini, z, tms).toPoint()
    #                     endPoint = Tile(xfin, yfin, z, tms).toPoint()
                        iniPoint = Tile(xini, yini, z).toPoint()
                        endPoint = Tile(xfin, yfin, z).toPoint()
                        
                        # Establish drawing window
                        self.settings.setExtent(self.projector.transform(QgsRectangle(iniPoint, endPoint)))
        
                        # Create and initialize image
                        image = QImage(self.settings.outputSize(), QImage.Format_ARGB32)
                        image.fill(Qt.transparent)
                        image.setDotsPerMeterX(dpm)
                        image.setDotsPerMeterY(dpm)
                 
                        # Paint map
                        painter = QPainter(image)
                        job = QgsMapRendererCustomPainterJob(self.settings, painter)
                        job.renderSynchronously()
                        # This increases plugin stability with very little impact on performance
                        QCoreApplication.processEvents()
                        # QCoreApplication.sendPostedEvents()
                        painter.end()
    
                        # MacroTile loop
                        i = 0
                        while i < self.macroTileSize:
                            # Test for interrupt in MacroTile loop
                            self.mutex.lock()
                            s = self.stopMe
                            self.mutex.unlock()
                            if s == 1:
                                self.interrupted = True
                                return

                            if (y + i > ymax):
                                break
                            else:
                                tmpImage = image.copy(self.width, self.height + (self.height*i), self.width, self.height)
            
                                if self.skipBlankTiles:
                                    is_blank = (tmpImage == blank_image)
                                else:
                                    is_blank = False
                                
                                if is_blank:
                                    self.blank_count += 1
                                else:
                                    tile_y = y+i
                                    if self.tmsConvention:
                                        tile_y = (1 << z) - tile_y - 1
                                    self.writer.writeTile(Tile(x, tile_y, z), tmpImage, self.fileFormat, self.quality)
                                    self.tile_count += 1
                                
                                self.updateProgress.emit(self.tile_count, self.blank_count)
                                del tmpImage
                                
                                i += 1
                                
                            # end of MacroTile loop
                            
                        y += i
    
                        # end of row loop
    
                    x += 1
                    # end of column loop

                #end of zoom level loop
        except:
            trace("At: %s" % datetime.datetime.now())
            trace("Unexpected error: %s" % sys.exc_info()[0])
            raise
        return 
    

def trace(msg):
    traceFile = "%s/qtiles_trace.txt" % os.path.dirname(os.path.realpath(__file__))
    with open(traceFile, 'a') as output:
        output.write("%s\n" % msg)
        output.close()
    

class MyTemplate(Template):
    delimiter = '@@'

    def __init__(self, templateString):
        Template.__init__(self, templateString)
