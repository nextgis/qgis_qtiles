# -*- coding: utf-8 -*-

#******************************************************************************
#
# QTiles
# ---------------------------------------------------------
# Generates tiles from QGIS project
#
# Copyright (C) 2012 Alexander Bruy (alexander.bruy@gmail.com)
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
import zipfile
from string import Template

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from qgis.core import *

from tile import Tile

import resources_rc

class TilingThread(QThread):
  rangeChanged = pyqtSignal(str, int)
  updateProgress = pyqtSignal()
  processFinished = pyqtSignal()
  processInterrupted = pyqtSignal()

  def __init__(self, layers, extent, minZoom, maxZoom, width, height, outputPath, rootDir, antialiasing, tmsConvention, mapUrl, viewer):
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
    self.rootDir = rootDir if not rootDir else QString("tileset_%1").arg(unicode(time.time()).split(".")[0])

    self.antialias = antialiasing
    self.tmsConvention = tmsConvention

    self.mapurl = mapUrl
    self.viewer = viewer

    self.interrupted = False
    self.tiles = []

    myRed = QgsProject.instance().readNumEntry("Gui", "/CanvasColorRedPart", 255)[0]
    myGreen = QgsProject.instance().readNumEntry("Gui", "/CanvasColorGreenPart", 255)[0]
    myBlue = QgsProject.instance().readNumEntry("Gui", "/CanvasColorBluePart", 255)[0]

    if int(QT_VERSION_STR[2]) >= 8:
      self.color = QColor(myRed, myGreen, myBlue)
    else:
      self.color = qRgb(myRed, myGreen, myBlue)

    self.image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)

    self.projector = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"),
                                            QgsCoordinateReferenceSystem("EPSG:3395")
                                           )

    self.scaleCalc = QgsScaleCalculator()
    self.scaleCalc.setDpi(self.image.logicalDpiX())
    self.scaleCalc.setMapUnits(QgsCoordinateReferenceSystem("EPSG:3395").mapUnits())

    self.labeling = QgsPalLabeling()
    self.renderer = QgsMapRenderer()
    self.renderer.setOutputSize(self.image.size(), self.image.logicalDpiX())
    self.renderer.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:3395"))
    self.renderer.setProjectionsEnabled(True)
    self.renderer.setLabelingEngine(self.labeling)
    self.renderer.setLayerSet(self.layers)

  def run(self):
    self.mutex.lock()
    self.stopMe = 0
    self.mutex.unlock()

    # prepare output
    if self.output.isDir():
      self.zip = None
      self.tmp = None
      if self.mapurl:
        self.writeMapurlFile()

      if self.viewer:
        self.writeLeafletViewer()
    else:
      self.zip = zipfile.ZipFile(unicode(self.output.absoluteFilePath()), "w")
      self.tmp = QTemporaryFile()
      self.tmp.setAutoRemove(False)
      self.tmp.open(QIODevice.WriteOnly)
      self.tempFileName = self.tmp.fileName()

    self.rangeChanged.emit(self.tr("Searching tiles..."), 0)

    useTMS = 1
    if self.tmsConvention:
      useTMS = -1

    self.countTiles(Tile(0, 0, 0, useTMS))

    if self.interrupted:
      #del self.tiles[:]
      #self.tiles = None

      if self.zip is not None:
        self.zip.close()
        self.zip = None

        self.tmp.close()
        self.tmp.remove()
        self.tmp = None

      self.processInterrupted.emit()

    self.rangeChanged.emit(self.tr("Rendering: %v from %m (%p%)"), len(self.tiles))

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

    if self.zip is not None:
      self.zip.close()
      self.zip = None

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
    filePath = QString("%1/%2.mapurl").arg(self.output.absoluteFilePath()).arg(self.rootDir)
    tileServer = "tms" if self.tmsConvention else "google"
    with open(filePath, "w") as mapurl:
      mapurl.write("%s=%s\n" % ("url", self.rootDir + "/ZZZ/XXX/YYY.png"))
      mapurl.write("%s=%s\n" % ("minzoom", self.minZoom))
      mapurl.write("%s=%s\n" % ("maxzoom", self.maxZoom))
      mapurl.write("%s=%f %f\n" % ("center", self.extent.center().x(), self.extent.center().y()))
      mapurl.write("%s=%s\n" % ("type", tileServer))

  def writeLeafletViewer(self):
    templateFile = QFile(":/resources/viewer.html")
    if templateFile.open(QIODevice.ReadOnly | QIODevice.Text):
      viewer = MyTemplate(unicode(templateFile.readAll()))
      tilesDir = unicode(QString("%1/%2").arg(self.output.absoluteFilePath()).arg(self.rootDir))
      useTMS = "true" if self.tmsConvention else "false"
      substitutions = {"tilesdir"    : tilesDir,
                       "tilesetname" : self.rootDir,
                       "tms"         : useTMS,
                       "centerx"     : self.extent.center().x(),
                       "centery"     : self.extent.center().y(),
                       "avgzoom"     : (self.maxZoom + self.minZoom) / 2,
                       "maxzoom"     : self.maxZoom
                      }

      filePath = QString("%1/%2.html").arg(self.output.absoluteFilePath()).arg(self.rootDir)
      with open(filePath, "w") as fOut:
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

          subTile = Tile(x, y, tile.z +1, tile.tms)
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
    path = QString("%1/%2/%3").arg(self.rootDir).arg(tile.z).arg(tile.x)
    if self.output.isDir():
      dirPath = QString("%1/%2").arg(self.output.absoluteFilePath()).arg(path)
      QDir().mkpath(dirPath)
      self.image.save(QString("%1/%2.png").arg(dirPath).arg(tile.y), "PNG")
    else:
      self.image.save(self.tempFileName, "PNG")
      self.tmp.close()

      tilePath = QString("%1/%2.png").arg(path).arg(tile.y)
      self.zip.write(unicode(self.tempFileName), unicode(tilePath).encode("utf8"))

class MyTemplate(Template):
  delimiter = "@"

  def __init__(self, templateString):
      Template.__init__(self, templateString)
