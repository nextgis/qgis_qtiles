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
import codecs
import json
import time
from string import Template
from typing import List

from qgis.core import (
    QgsMapLayer,
    QgsMapRendererCustomPainterJob,
    QgsMapSettings,
    QgsMessageLog,
    QgsProject,
    QgsRectangle,
    QgsScaleCalculator,
)
from qgis.PyQt.QtCore import (
    QFile,
    QFileInfo,
    QIODevice,
    QMutex,
    Qt,
    QThread,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QColor, QImage, QPainter
from qgis.PyQt.QtWidgets import *

from . import resources_rc  # noqa: F401
from .compat import (
    QGIS_VERSION_3,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMessageLogInfo,
)
from .tile import Tile
from .writers import *


def printQtilesLog(msg, level=QgsMessageLogInfo):
    QgsMessageLog.logMessage(msg, "QTiles", level)


class TilingThread(QThread):
    rangeChanged = pyqtSignal(str, int)
    updateProgress = pyqtSignal()
    processFinished = pyqtSignal()
    processInterrupted = pyqtSignal()
    threshold = pyqtSignal(int)

    warring_threshold_tiles_count = 10000

    def __init__(
        self,
        tiles: List[Tile],
        layers: List[QgsMapLayer],
        extent: QgsRectangle,
        minZoom: int,
        maxZoom: int,
        width: int,
        height: int,
        transp: int,
        quality: int,
        format: str,
        outputPath: QFileInfo,
        rootDir: str,
        antialiasing: bool,
        tmsConvention: bool,
        mbtilesCompression: bool,
        jsonFile: bool,
        overview: bool,
        mapUrl: bool,
        viewer: bool,
    ) -> None:
        QThread.__init__(self, QThread.currentThread())
        self.mutex = QMutex()
        self.confirmMutex = QMutex()
        self.stopMe = 0
        self.interrupted = False
        self.tiles = tiles
        self.layers = layers
        self.extent = extent
        self.minZoom = minZoom
        self.maxZoom = maxZoom
        self.output = outputPath
        self.width = width
        if rootDir:
            self.rootDir = rootDir
        else:
            self.rootDir = "tileset_%s" % str(time.time()).split(".")[0]
        self.antialias = antialiasing
        self.tmsConvention = tmsConvention
        self.mbtilesCompression = mbtilesCompression
        self.format = format
        self.quality = quality
        self.jsonFile = jsonFile
        self.overview = overview
        self.mapurl = mapUrl
        self.viewer = viewer
        if self.output.isDir():
            self.mode = "DIR"
        elif self.output.suffix().lower() == "zip":
            self.mode = "ZIP"
        elif self.output.suffix().lower() == "ngrc":
            self.mode = "NGM"
        elif self.output.suffix().lower() == "mbtiles":
            self.mode = "MBTILES"
            self.tmsConvention = True
        self.interrupted = False
        self.layersId = []
        for layer in self.layers:
            self.layersId.append(layer.id())
        myRed = QgsProject.instance().readNumEntry(
            "Gui", "/CanvasColorRedPart", 255
        )[0]
        myGreen = QgsProject.instance().readNumEntry(
            "Gui", "/CanvasColorGreenPart", 255
        )[0]
        myBlue = QgsProject.instance().readNumEntry(
            "Gui", "/CanvasColorBluePart", 255
        )[0]
        self.color = QColor(myRed, myGreen, myBlue, transp)
        image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        self.projector = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem.fromEpsgId(4326),
            QgsCoordinateReferenceSystem.fromEpsgId(3395),
        )
        self.scaleCalc = QgsScaleCalculator()
        self.scaleCalc.setDpi(image.logicalDpiX())
        self.scaleCalc.setMapUnits(
            QgsCoordinateReferenceSystem.fromEpsgId(3395).mapUnits()
        )
        self.settings = QgsMapSettings()
        self.settings.setBackgroundColor(self.color)

        if not QGIS_VERSION_3:
            self.settings.setCrsTransformEnabled(True)

        self.settings.setOutputDpi(image.logicalDpiX())
        self.settings.setOutputImageFormat(QImage.Format_ARGB32_Premultiplied)
        self.settings.setDestinationCrs(
            QgsCoordinateReferenceSystem.fromEpsgId(3395)
        )
        self.settings.setOutputSize(image.size())

        if QGIS_VERSION_3:
            self.settings.setLayers(self.layers)
        else:
            self.settings.setLayers(self.layersId)

        if not QGIS_VERSION_3:
            self.settings.setMapUnits(
                QgsCoordinateReferenceSystem.fromEpsgId(3395).mapUnits()
            )

        if self.antialias:
            self.settings.setFlag(QgsMapSettings.Antialiasing, True)
        else:
            self.settings.setFlag(QgsMapSettings.DrawLabeling, True)

    def run(self) -> None:
        self.mutex.lock()
        self.stopMe = 0
        self.mutex.unlock()
        if self.mode == "DIR":
            self.writer = DirectoryWriter(self.output, self.rootDir)
            if self.mapurl:
                self.writeMapurlFile()
            if self.viewer:
                self.writeLeafletViewer()
        elif self.mode == "ZIP":
            self.writer = ZipWriter(self.output, self.rootDir)
        elif self.mode == "NGM":
            self.writer = NGMArchiveWriter(self.output, self.rootDir)
        elif self.mode == "MBTILES":
            self.writer = MBTilesWriter(
                self.output,
                self.rootDir,
                self.format,
                self.minZoom,
                self.maxZoom,
                self.extent,
                self.mbtilesCompression,
            )
        if self.jsonFile:
            self.writeJsonFile()
        if self.overview:
            self.writeOverviewFile()
        self.rangeChanged.emit(self.tr("Searching tiles..."), 0)

        if self.interrupted:
            del self.tiles[:]
            self.tiles = None
            self.processInterrupted.emit()
        self.rangeChanged.emit(
            self.tr("Rendering: %v from %m (%p%)"), len(self.tiles)
        )

        if len(self.tiles) > self.warring_threshold_tiles_count:
            self.confirmMutex.lock()
            self.threshold.emit(self.warring_threshold_tiles_count)

        self.confirmMutex.lock()
        if self.interrupted:
            self.processInterrupted.emit()
            return

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

    def stop(self) -> None:
        self.mutex.lock()
        self.stopMe = 1
        self.mutex.unlock()
        QThread.wait(self)

    def confirmContinue(self) -> None:
        self.confirmMutex.unlock()

    def confirmStop(self) -> None:
        self.interrupted = True
        self.confirmMutex.unlock()

    def writeJsonFile(self) -> None:
        filePath = "%s.json" % self.output.absoluteFilePath()
        if self.mode == "DIR":
            filePath = "%s/%s.json" % (
                self.output.absoluteFilePath(),
                self.rootDir,
            )
        info = {
            "name": self.rootDir,
            "format": self.format.lower(),
            "minZoom": self.minZoom,
            "maxZoom": self.maxZoom,
            "bounds": str(self.extent.xMinimum())
            + ","
            + str(self.extent.yMinimum())
            + ","
            + str(self.extent.xMaximum())
            + ","
            + str(self.extent.yMaximum()),
        }
        with open(filePath, "w") as f:
            f.write(json.dumps(info))

    def writeOverviewFile(self) -> None:
        self.settings.setExtent(self.projector.transform(self.extent))

        image = QImage(self.settings.outputSize(), QImage.Format_ARGB32)
        image.fill(Qt.transparent)

        dpm = round(self.settings.outputDpi() / 25.4 * 1000)
        image.setDotsPerMeterX(dpm)
        image.setDotsPerMeterY(dpm)

        # job = QgsMapRendererSequentialJob(self.settings)
        # job.start()
        # job.waitForFinished()
        # image = job.renderedImage()

        painter = QPainter(image)
        job = QgsMapRendererCustomPainterJob(self.settings, painter)
        job.renderSynchronously()
        painter.end()

        filePath = "%s.%s" % (
            self.output.absoluteFilePath(),
            self.format.lower(),
        )
        if self.mode == "DIR":
            filePath = "%s/%s.%s" % (
                self.output.absoluteFilePath(),
                self.rootDir,
                self.format.lower(),
            )
        image.save(filePath, self.format, self.quality)

    def writeMapurlFile(self) -> None:
        filePath = "%s/%s.mapurl" % (
            self.output.absoluteFilePath(),
            self.rootDir,
        )
        tileServer = "tms" if self.tmsConvention else "google"
        with open(filePath, "w") as mapurl:
            mapurl.write(
                "%s=%s\n" % ("url", self.rootDir + "/ZZZ/XXX/YYY.png")
            )
            mapurl.write("%s=%s\n" % ("minzoom", self.minZoom))
            mapurl.write("%s=%s\n" % ("maxzoom", self.maxZoom))
            mapurl.write(
                "%s=%f %f\n"
                % (
                    "center",
                    self.extent.center().x(),
                    self.extent.center().y(),
                )
            )
            mapurl.write("%s=%s\n" % ("type", tileServer))

    def writeLeafletViewer(self) -> None:
        templateFile = QFile(":/plugins/qtiles/resources/viewer.html")
        if templateFile.open(QIODevice.ReadOnly | QIODevice.Text):
            viewer = MyTemplate(str(templateFile.readAll()))

            tilesDir = "%s/%s" % (self.output.absoluteFilePath(), self.rootDir)
            useTMS = "true" if self.tmsConvention else "false"
            substitutions = {
                "tilesdir": tilesDir,
                "tilesext": self.format.lower(),
                "tilesetname": self.rootDir,
                "tms": useTMS,
                "centerx": self.extent.center().x(),
                "centery": self.extent.center().y(),
                "avgzoom": (self.maxZoom + self.minZoom) / 2,
                "maxzoom": self.maxZoom,
            }

            filePath = "%s/%s.html" % (
                self.output.absoluteFilePath(),
                self.rootDir,
            )
            with codecs.open(filePath, "w", "utf-8") as fOut:
                fOut.write(viewer.substitute(substitutions))
            templateFile.close()

    def render(self, tile: Tile) -> None:
        # scale = self.scaleCalc.calculate(
        #    self.projector.transform(tile.toRectangle()), self.width)

        self.settings.setExtent(self.projector.transform(tile.toRectangle()))

        image = QImage(self.settings.outputSize(), QImage.Format_ARGB32)
        image.fill(Qt.transparent)

        dpm = round(self.settings.outputDpi() / 25.4 * 1000)
        image.setDotsPerMeterX(dpm)
        image.setDotsPerMeterY(dpm)

        # job = QgsMapRendererSequentialJob(self.settings)
        # job.start()
        # job.waitForFinished()
        # image = job.renderedImage()

        painter = QPainter(image)
        job = QgsMapRendererCustomPainterJob(self.settings, painter)
        job.renderSynchronously()
        painter.end()
        self.writer.writeTile(tile, image, self.format, self.quality)


class MyTemplate(Template):
    delimiter = "@"

    def __init__(self, templateString):
        Template.__init__(self, templateString)
