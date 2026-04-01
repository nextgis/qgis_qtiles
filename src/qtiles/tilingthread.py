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
from typing import List, Optional

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsLabelingEngineSettings,
    QgsMapLayer,
    QgsMapRendererCustomPainterJob,
    QgsMapSettings,
    QgsProject,
    QgsRectangle,
)
from qgis.PyQt.QtCore import (
    QMutex,
    Qt,
    QThread,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QColor, QImage, QPainter
from qgis.utils import iface

from qtiles import resources_rc  # noqa: F401
from qtiles.core.exceptions import TileGenerationError, TileGenerationWarning
from qtiles.core.logging import logger
from qtiles.tile import Tile
from qtiles.writers.enums import TilesWriterMode
from qtiles.writers.save_tiles_options import SaveTilesOptions
from qtiles.writers.tiles_artifacts_writer import TilesetArtifactsWriter
from qtiles.writers.tiles_writer_factory import TilesWriterFactory


class TilingThread(QThread):
    """
    Background thread for generating map tiles.
    """

    rangeChanged = pyqtSignal(str, int)
    updateProgress = pyqtSignal()
    processFinished = pyqtSignal()
    processInterrupted = pyqtSignal()
    processError = pyqtSignal()

    def __init__(
        self,
        tiles: List[Tile],
        layers: List[QgsMapLayer],
        writer_mode: TilesWriterMode,
        extent: QgsRectangle,
        min_zoom: int,
        max_zoom: int,
        tile_size: int,
        quality: int,
        dpi: int,
        format: str,
        output_path: Path,
        root_dir: str,
        antialiasing: bool,
        is_background_transparent: bool,
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
        :param writer_mode: Selected tiles writer mode.
        :param extent: The geographical extent for tile generation.
        :param min_zoom: The minimum zoom level.
        :param max_zoom: The maximum zoom level.
        :param tile_size: The size of each tile in pixels (square tiles).
        :param quality: The quality level for image compression.
        :param dpi: Output DPI used for map rendering.
        :param format: The output format (e.g., PNG, JPG).
        :param output_path: The file path for saving the tiles.
        :param root_dir: The root directory for output files.
        :param antialiasing: Whether to enable antialiasing.
        :param is_background_transparent: Whether the tile background
            should be rendered as transparent.
        :param tms_convention: Whether to use TMS naming convention.
        :param mbtiles_compression: Whether to enable MBTiles compression.
        :param json_file: Whether to generate a JSON metadata file.
        :param overview: Whether to generate an overview file.
        :param map_url: Whether to include a map URL in the output.
        :param viewer: Whether to generate a viewer for the tiles.
        """
        super().__init__()
        self.mutex = QMutex()
        self.stopMe = 0
        self.interrupted = False
        self.tiles = tiles
        self.writer_mode = writer_mode
        self.extent = extent
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.output_path = output_path
        self.root_dir = root_dir
        self.tms_convention = tms_convention
        self.mbtiles_compression = mbtiles_compression
        self.format = format
        self.quality = quality
        self.dpi = dpi
        self.json_file = json_file
        self.overview = overview
        self.mapurl = map_url
        self.viewer = viewer
        self.writer = None
        self.error: Optional[TileGenerationError] = None
        self.warning: Optional[TileGenerationWarning] = None

        self.layersId = []
        for layer in layers:
            self.layersId.append(layer.id())

        image = QImage(
            tile_size, tile_size, QImage.Format.Format_ARGB32_Premultiplied
        )

        self.projector = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem.fromEpsgId(4326),
            QgsCoordinateReferenceSystem.fromEpsgId(3857),
            QgsProject.instance(),
        )

        canvas_settings = iface.mapCanvas().mapSettings()
        self.render_settings = QgsMapSettings(canvas_settings)

        self.render_settings.setDestinationCrs(
            QgsCoordinateReferenceSystem.fromEpsgId(3857)
        )
        self.render_settings.setLayers(layers)
        self.render_settings.setOutputDpi(self.dpi)
        self.render_settings.setOutputSize(image.size())
        self.render_settings.setDevicePixelRatio(1.0)

        if antialiasing:
            self.render_settings.setFlag(QgsMapSettings.Antialiasing, True)

        self.render_settings.setFlag(QgsMapSettings.DrawLabeling, True)
        self.render_settings.setFlag(
            QgsMapSettings.RenderMapTile,
            True,
        )

        labeling_settings = self.render_settings.labelingEngineSettings()
        labeling_settings.setFlag(
            QgsLabelingEngineSettings.UsePartialCandidates, False
        )
        self.render_settings.setLabelingEngineSettings(labeling_settings)

        background_red = QgsProject.instance().readNumEntry(
            "Gui", "/CanvasColorRedPart", 255
        )[0]
        background_green = QgsProject.instance().readNumEntry(
            "Gui", "/CanvasColorGreenPart", 255
        )[0]
        background_blue = QgsProject.instance().readNumEntry(
            "Gui", "/CanvasColorBluePart", 255
        )[0]

        alpha = 0 if is_background_transparent else 255
        background_color = QColor(
            background_red,
            background_green,
            background_blue,
            alpha,
        )

        self.render_settings.setBackgroundColor(background_color)

        self.image = QImage(
            self.render_settings.outputSize(),
            QImage.Format.Format_ARGB32_Premultiplied,
        )

        dpm = round(self.dpi / 25.4 * 1000)
        self.image.setDotsPerMeterX(dpm)
        self.image.setDotsPerMeterY(dpm)

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

        self.interrupted = False
        self.error = None
        self.warning = None

        try:
            self._run_generation()
        except TileGenerationWarning as warning:
            self.warning = warning
        except TileGenerationError as error:
            self.error = error
            self.processError.emit()
            return
        except Exception as error:
            wrapped_error = TileGenerationError(
                log_message="Unexpected error during tile generation.",
                user_message=self.tr("Failed to generate the tile set."),
            )
            wrapped_error.__cause__ = error
            self.error = wrapped_error
            self.processError.emit()
            return
        finally:
            if self.interrupted or self.error is not None:
                self._cancel_writer()
            self.writer = None

        if self.interrupted:
            self.processInterrupted.emit()
            return

        self.processFinished.emit()

    def _run_generation(self) -> None:
        """
        Execute tile rendering and artifact generation.
        """
        overview_map_settings = QgsMapSettings(self.render_settings)

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

        self.writer = TilesWriterFactory.create(self.writer_mode, save_options)

        if self._is_stop_requested():
            self.interrupted = True
            return

        self.rangeChanged.emit(
            self.tr("Rendering: %v from %m (%p%)"), len(self.tiles)
        )
        for tile in self.tiles:
            if self._is_stop_requested():
                self.interrupted = True
                return

            self.render(tile)
            self.updateProgress.emit()

        if self._is_stop_requested():
            self.interrupted = True
            return

        self.writer.finalize()

        if self._is_stop_requested():
            self.interrupted = True
            return

        artifacts_writer = TilesetArtifactsWriter(save_options)
        artifacts_writer.write()

        if self._is_stop_requested():
            self.interrupted = True
            return

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

    def _is_stop_requested(self) -> bool:
        """
        Checks whether the thread was requested to stop.

        :returns: True if cancellation was requested, otherwise False.
        """
        self.mutex.lock()
        stop_me = self.stopMe
        self.mutex.unlock()
        return stop_me == 1

    def _cancel_writer(self) -> None:
        """
        Cancels the active writer and releases its resources.

        :returns: None
        """
        if self.writer is None:
            return

        try:
            self.writer.cancel()
        except Exception:
            logger.exception("Failed to cancel tiles writer.")

    def render(self, tile: Tile) -> None:
        """
        Renders a single tile based on the provided tile object.

        This method processes a tile by rendering it to an image,
        using map settings and transforms.
        """
        tile_extent = self.projector.transform(tile.to_rectangle())
        self.render_settings.setExtent(tile_extent)

        self.image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(self.image)
        job = QgsMapRendererCustomPainterJob(self.render_settings, painter)
        job.renderSynchronously()
        painter.end()

        self.writer.write_tile(tile, self.image, self.format, self.quality)
