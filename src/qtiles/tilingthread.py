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
    QIODevice,
    QMutex,
    Qt,
    QThread,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QColor, QImage, QPainter
from qgis.PyQt.QtWidgets import *

from qtiles.qtiles_utils import create_viewer_directory

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
    """
    Background thread for generating map tiles.
    """

    rangeChanged = pyqtSignal(str, int)
    updateProgress = pyqtSignal()
    processFinished = pyqtSignal()
    processInterrupted = pyqtSignal()

    def __init__(
        self,
        tiles: List[Tile],
        layers: List[QgsMapLayer],
        extent: QgsRectangle,
        min_zoom: int,
        max_zoom: int,
        width: int,
        height: int,
        transp: int,
        quality: int,
        format: str,
        output_path: Path,
        root_dir: str,
        antialiasing: bool,
        tms_convention: bool,
        mbtiles_compression: bool,
        json_file: bool,
        overview: bool,
        map_url: bool,
        viewer: bool,
    ) -> None:
        """
        Initializes the TilingThread with the given parameters.

        :param tiles: A list of tiles to generate.
        :param layers: A list of map layers to render.
        :param extent: The geographical extent for tile generation.
        :param min_zoom: The minimum zoom level.
        :param max_zoom: The maximum zoom level.
        :param width: The width of each tile in pixels.
        :param height: The height of each tile in pixels.
        :param transp: The transparency level for tiles.
        :param quality: The quality level for image compression.
        :param format: The output format (e.g., PNG, JPG).
        :param output_path: The file path for saving the tiles.
        :param root_dir: The root directory for output files.
        :param antialiasing: Whether to enable antialiasing.
        :param tms_convention: Whether to use TMS naming convention.
        :param mbtiles_compression: Whether to enable MBTiles compression.
        :param json_file: Whether to generate a JSON metadata file.
        :param overview: Whether to generate an overview file.
        :param map_url: Whether to include a map URL in the output.
        :param viewer: Whether to generate a viewer for the tiles.
        """
        super().__init__()
        self.mutex = QMutex()
        self.confirmMutex = QMutex()
        self.stopMe = 0
        self.interrupted = False
        self.tiles = tiles
        self.layers = layers
        self.extent = extent
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.output_path = output_path
        self.width = width
        if root_dir:
            self.root_dir = root_dir
        else:
            self.root_dir = "tileset_%s" % str(time.time()).split(".")[0]
        self.antialias = antialiasing
        self.tms_convention = tms_convention
        self.mbtiles_compression = mbtiles_compression
        self.format = format
        self.quality = quality
        self.json_file = json_file
        self.overview = overview
        self.mapurl = map_url
        self.viewer = viewer

        if self.output_path.is_dir():
            self.mode = "DIR"
        elif self.output_path.suffix.lower() == ".zip":
            self.mode = "ZIP"
        elif self.output_path.suffix.lower() == ".ngrc":
            self.mode = "NGM"
        elif self.output_path.suffix.lower() == ".mbtiles":
            self.mode = "MBTILES"
            self.tms_convention = True

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
        image = QImage(
            width, height, QImage.Format.Format_ARGB32_Premultiplied
        )
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
        self.settings.setOutputImageFormat(
            QImage.Format.Format_ARGB32_Premultiplied
        )
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
        """
        Starts the tile generation process in the background thread.
        The process renders tiles and writes them to the specified output format.
        If the tile count exceeds the threshold, the user is asked to confirm continuation.
        The method processes tiles sequentially until either
        all tiles are generated or the process is interrupted.
        """
        self.mutex.lock()
        self.stopMe = 0
        self.mutex.unlock()
        if self.mode == "DIR":
            self.writer = DirectoryWriter(self.output_path, self.root_dir)
            if self.mapurl:
                self.writeMapurlFile()
            if self.viewer:
                self.writeLeafletViewer()
        elif self.mode == "ZIP":
            self.writer = ZipWriter(self.output_path, self.root_dir)
        elif self.mode == "NGM":
            self.writer = NGMArchiveWriter(self.output_path, self.root_dir)
        elif self.mode == "MBTILES":
            self.writer = MBTilesWriter(
                self.output_path,
                self.root_dir,
                self.format,
                self.min_zoom,
                self.max_zoom,
                self.extent,
                self.mbtiles_compression,
            )
        if self.json_file:
            self.writeJsonFile()
        if self.overview:
            self.writeOverviewFile()
        self.rangeChanged.emit(self.tr("Searching tiles..."), 0)

        if self.interrupted:
            self.tiles.clear()
            self.processInterrupted.emit()
            return

        self.rangeChanged.emit(
            self.tr("Rendering: %v from %m (%p%)"), len(self.tiles)
        )

        self.confirmMutex.lock()
        if self.interrupted:
            self.processInterrupted.emit()
            return

        for tile in self.tiles:
            self.render(tile)
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
        """
        Stops the tile generation process.

        This method sets a flag to interrupt the thread and halt the
        generation of remaining tiles.
        """
        self.mutex.lock()
        self.stopMe = 1
        self.mutex.unlock()
        QThread.wait(self)

    def writeJsonFile(self) -> None:
        """
        Writes a JSON metadata file that describes the tile set.

        The file contains information about the tile set,
        such as the format, zoom levels, and geographical bounds.
        """
        if self.mode == "DIR":
            file_path = self.output_path / f"{self.root_dir}.json"
        else:
            base_name = self.output_path.stem
            file_path = self.output_path.parent / f"{base_name}.json"

        info = {
            "name": self.root_dir,
            "format": self.format.lower(),
            "minZoom": self.min_zoom,
            "maxZoom": self.max_zoom,
            "bounds": str(self.extent.xMinimum())
            + ","
            + str(self.extent.yMinimum())
            + ","
            + str(self.extent.xMaximum())
            + ","
            + str(self.extent.yMaximum()),
        }

        with open(str(file_path), "w", encoding="utf-8") as json_file:
            json.dump(info, json_file)

    def writeOverviewFile(self) -> None:
        """
        Generates an overview image for the tile set.

        This image represents the entire geographical extent
        in a single image, useful for creating a preview of the tile set.
        """
        self.settings.setExtent(self.projector.transform(self.extent))

        image = QImage(self.settings.outputSize(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)

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

        if self.mode == "DIR":
            file_path = (
                self.output_path / f"{self.root_dir}.{self.format.lower()}"
            )
        else:
            base_name = self.output_path.stem
            file_path = (
                self.output_path.parent / f"{base_name}.{self.format.lower()}"
            )

        image.save(str(file_path), self.format, self.quality)

    def writeMapurlFile(self) -> None:
        """
        Writes a `.mapurl` file that includes details
        on how to access the tile server.

        The map URL file contains information about the tile format,
        zoom levels, and server convention (TMS or Google).
        """
        file_path = self.output_path / f"{self.root_dir}.mapurl"
        tileServer = "tms" if self.tms_convention else "google"
        with open(str(file_path), "w", encoding="utf-8") as mapurl:
            mapurl.write(
                "%s=%s\n" % ("url", self.root_dir + "/ZZZ/XXX/YYY.png")
            )
            mapurl.write("%s=%s\n" % ("minzoom", self.min_zoom))
            mapurl.write("%s=%s\n" % ("maxzoom", self.max_zoom))
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
        """
        Writes an HTML file for a Leaflet viewer to visualize the generated tiles.

        The viewer allows users to interact
        with the tiles and navigate through the map.
        """
        template_file = QFile(":/plugins/qtiles/resources/viewer.html")
        if not template_file.open(QIODevice.OpenModeFlag.ReadOnly):
            return

        html = template_file.readAll().data().decode()
        template_file.close()
        viewer_template = MyTemplate(html)

        viewer_dir = self.output_path / f"{self.root_dir}_viewer"

        create_viewer_directory(viewer_dir)

        tiles_dir_relative = f"../{self.root_dir}"
        substitutions = {
            "tilesdir": tiles_dir_relative,
            "tilesext": self.format.lower(),
            "tilesetname": self.root_dir,
            "tms": "true" if self.tms_convention else "false",
            "centerx": self.extent.center().x(),
            "centery": self.extent.center().y(),
            "avgzoom": (self.max_zoom + self.min_zoom) / 2,
            "maxzoom": self.max_zoom,
        }

        output_html = viewer_template.substitute(substitutions)
        index_path = viewer_dir / "index.html"
        with open(str(index_path), "wb") as html_viewer:
            html_viewer.write(output_html.encode("utf-8"))

    def render(self, tile: Tile) -> None:
        """
        Renders a single tile based on the provided tile object.

        This method processes a tile by rendering it to an image,
        using map settings and transforms.
        """
        # scale = self.scaleCalc.calculate(
        #    self.projector.transform(tile.toRectangle()), self.width)

        self.settings.setExtent(self.projector.transform(tile.toRectangle()))

        image = QImage(self.settings.outputSize(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)

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
    """
    A subclass of Python's built-in Template class
    that uses a custom delimiter "@" for variable substitution.

    This class allows template substitution
    using the "@" symbol instead of the default "${}" delimiter.
    It is used to customize the rendering of template strings
    for generating HTML files, specifically in the context of creating
    a Leaflet viewer for the tile generation process.
    """

    delimiter = "@"

    def __init__(self, template_string: str) -> None:
        """
        Initializes the MyTemplate class with the provided template string.

        :param templateString: The template string to be processed.
                               This string can contain placeholders that will be
                               replaced with actual values during template substitution.
        """
        Template.__init__(self, template_string)
