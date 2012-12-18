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
import zipfile

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from qgis.core import *

from tile import Tile

class TilingThread(QThread):
  rangeChanged = pyqtSignal(str, int)
  updateProgress = pyqtSignal()
  processFinished = pyqtSignal()
  processInterrupted = pyqtSignal()

  rootDir = "Mapnik"

  def __init__(self, layers, extent, minZoom, maxZoom, width, height, outputPath):
    QThread.__init__(self, QThread.currentThread())
    self.mutex = QMutex()
    self.stopMe = 0
    self.interrupted = False

    self.layers = layers
    self.extent = extent
    self.minZoom = minZoom
    self.maxZoom = maxZoom
    self.output = outputPath

    self.interrupted = False
    self.tiles = []

    self.image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)

    self.projector = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"),
                                            QgsCoordinateReferenceSystem("EPSG:3395")
                                           )

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
    else:
      self.zip = zipfile.ZipFile(unicode(self.output.absoluteFilePath()), "w")
      self.tmp = QTemporaryFile()
      self.tmp.setAutoRemove(False)
      self.tmp.open(QIODevice.WriteOnly)
      self.tempFileName = self.tmp.fileName()

    self.rangeChanged.emit(self.tr("Searching tiles..."), 0)

    self.__countTiles(Tile())

    if self.interrupted:
      if self.zip is not None:
        self.zip.close()
        self.zip = None

        self.tmp.close()
        self.tmp.remove()
        self.tmp = None

      self.processInterrupted.emit()

    self.rangeChanged.emit(self.tr("Rendering: %p%"), len(self.tiles))

    for t in self.tiles:
      self.__render(t)

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

  def __countTiles(self, tile):
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

          subTile = Tile(x, y, tile.z +1)
          self.__countTiles(subTile)

  def __render(self, tile):
    self.renderer.setExtent(self.projector.transform(tile.toRectangle()))
    latitude = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * float(tile.y) / float(math.pow(2, tile.z))))))
    resolution = 156543.034 * math.cos(latitude) / float(math.pow(2, tile.z))
    scale = self.image.logicalDpiX() * 39.37 * resolution
    #QgsMessageLog.logMessage(QString("Scale: %1").arg(scale), "QTiles")
    self.renderer.setScale(scale)
    self.image.fill(QColor(255, 255, 255, 0).rgb())
    painter = QPainter()
    painter.begin(self.image)
    self.renderer.render(painter)
    painter.end()

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
