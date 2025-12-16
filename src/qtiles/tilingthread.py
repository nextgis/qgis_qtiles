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
import time
from pathlib import Path
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
    QMutex,
    Qt,
    QThread,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QColor, QImage, QPainter
from qgis.PyQt.QtWidgets import *

from qtiles.writers.enums import TilesWriterMode
from qtiles.writers.save_tiles_options import SaveTilesOptions
from qtiles.writers.tiles_artifacts_writer import TilesetArtifactsWriter
from qtiles.writers.tiles_writer_factory import TilesWriterFactory

from . import resources_rc  # noqa: F401
from .compat import (
    QGIS_VERSION_3,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMessageLogInfo,
)
from .tile import Tile


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

        self.mode = TilesWriterMode.from_output_path(self.output_path)

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
        self.settings.setExtent(self.projector.transform(self.extent))
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

        Renders tiles sequentially and writes them using the selected
        tile writer; after rendering completes, auxiliary artifacts
        (overview, metadata, viewers) are generated if requested.
        """
        self.mutex.lock()
        self.stopMe = 0
        self.mutex.unlock()

        overview_map_settings = QgsMapSettings(self.settings)

        save_options = SaveTilesOptions(
            output_path=self.output_path,
            root_dir=self.root_dir,
            image_format=self.format,
            quality=self.quality,
            min_zoom=self.min_zoom,
            max_zoom=self.max_zoom,
            extent=self.extent,
            compression=self.mbtiles_compression,
            tms_convention=self.tms_convention,
            write_mapurl=self.mapurl,
            write_overview=self.overview,
            write_viewer=self.viewer,
            write_json_metadata=self.json_file,
            overview_map_settings=overview_map_settings,
        )

        self.writer = TilesWriterFactory.create(self.mode, save_options)

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

        overview_map_settings = QgsMapSettings(self.settings)

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

        artifacts_writer = TilesetArtifactsWriter(save_options)
        artifacts_writer.write()

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

    def render(self, tile: Tile) -> None:
        """
        Renders a single tile based on the provided tile object.

        This method processes a tile by rendering it to an image,
        using map settings and transforms.
        """
        self.settings.setExtent(self.projector.transform(tile.toRectangle()))

        image = QImage(self.settings.outputSize(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)

        dpm = round(self.settings.outputDpi() / 25.4 * 1000)
        image.setDotsPerMeterX(dpm)
        image.setDotsPerMeterY(dpm)

        painter = QPainter(image)
        job = QgsMapRendererCustomPainterJob(self.settings, painter)
        job.renderSynchronously()
        painter.end()
        self.writer.write_tile(tile, image, self.format, self.quality)
