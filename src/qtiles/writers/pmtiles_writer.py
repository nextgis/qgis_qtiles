from pathlib import Path
from typing import Optional

from qgis.core import QgsApplication, QgsRectangle
from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice
from qgis.PyQt.QtGui import QImage

from qtiles.external.pmtiles.tile import Compression, TileType, zxy_to_tileid
from qtiles.external.pmtiles.writer import Writer
from qtiles.tile import Tile
from qtiles.writers.abstract_tiles_writer import AbstractTilesWriter
from qtiles.writers.utils import ensure_operation_succeeded


class PMTilesWriter(AbstractTilesWriter):
    """
    Writes tiles into a PMTiles archive.
    """

    def __init__(
        self,
        *,
        output_path: Path,
        root_dir: str,
        image_format: str,
        min_zoom: int,
        max_zoom: int,
        extent: QgsRectangle,
    ) -> None:
        """
        Initializes PMTiles writer.

        :param output_path: Path to .pmtiles file.
        :type output_path: Path
        :param root_dir: Tileset name.
        :type root_dir: str
        :param image_format: Image format (e.g. 'PNG', 'JPEG').
        :type image_format: str
        :param min_zoom: Minimum zoom level.
        :type min_xoom: int
        :param max_zoom: Maximum zoom level.
        :type max_xoom: int
        :param extent: Geographic extent.
        :type extent: QgsRectangle
        """
        self.__output_path = output_path
        self.__root_dir = root_dir
        self.__image_format = image_format
        self.__min_zoom = min_zoom
        self.__max_zoom = max_zoom
        self.__extent = extent

        self.__file = open(self.__output_path, "wb")
        self.__writer = Writer(self.__file)

    def write_tile(
        self,
        tile: Tile,
        image: QImage,
        image_format: str,
        quality: int,
    ) -> None:
        """
        Writes a single tile into PMTiles archive.

        :param tile: Tile descriptor containing z, x, y coordinates.
        :type tile: Tile
        :param image: Rendered tile image.
        :type image: QImage
        :param image_format: Image format (e.g., 'PNG', 'JPEG').
        :type image_format: str
        :param quality: Image quality (0–100).
        :type quality: int

        :returns: None
        """
        data = QByteArray()
        buffer = QBuffer(data)
        # fmt: off
        ensure_operation_succeeded(
            buffer.open(QIODevice.OpenModeFlag.WriteOnly),
            log_message="Failed to open PMTiles buffer for tile encoding",
            user_message=QgsApplication.translate(
                "QTiles", "Failed to write one of the generated tiles."
            ),
            detail=QgsApplication.translate(
                "QTiles",
                "Could not allocate an in-memory buffer for PMTiles tile "
                "{z}/{x}/{y}."
            ).format(
                z=tile.z,
                x=tile.x,
                y=tile.y,
            ),
        )
        # fmt: on
        # fmt: off
        ensure_operation_succeeded(
            image.save(buffer, image_format, quality),
            log_message="Failed to encode tile image for PMTiles",
            user_message=QgsApplication.translate(
                "QTiles", "Failed to write one of the generated tiles."
            ),
            detail=QgsApplication.translate(
                "QTiles",
                "Tile {z}/{x}/{y} could not be encoded before writing "
                "to PMTiles."
            ).format(
                z=tile.z,
                x=tile.x,
                y=tile.y,
            ),
        )
        # fmt: on
        buffer.close()

        tile_id = zxy_to_tileid(tile.z, tile.x, tile.y)
        self.__writer.write_tile(tile_id, bytes(data))

    def finalize(self) -> None:
        """
        Finalizes PMTiles archive by writing header, directories and tile data.
        """
        writer = self.__writer
        if writer is None:
            self.__close_file()
            return

        if self.__image_format.upper() == "PNG":
            tile_type = TileType.PNG
            metadata_format = "png"
        else:
            tile_type = TileType.JPEG
            metadata_format = "jpeg"

        extent = self.__extent
        center = extent.center()

        header = {
            "tile_type": tile_type,
            "tile_compression": Compression.NONE,
            "min_lon_e7": int(extent.xMinimum() * 1e7),
            "min_lat_e7": int(extent.yMinimum() * 1e7),
            "max_lon_e7": int(extent.xMaximum() * 1e7),
            "max_lat_e7": int(extent.yMaximum() * 1e7),
            "center_lon_e7": int(center.x() * 1e7),
            "center_lat_e7": int(center.y() * 1e7),
            "center_zoom": self.__min_zoom,
        }

        metadata = {
            "name": self.__root_dir,
            "format": metadata_format,
            "bounds": [
                extent.xMinimum(),
                extent.yMinimum(),
                extent.xMaximum(),
                extent.yMaximum(),
            ],
            "minzoom": self.__min_zoom,
            "maxzoom": self.__max_zoom,
            "attribution": "Generated by QTiles (NextGIS)",
        }

        try:
            writer.finalize(header, metadata)
        finally:
            self.__writer = None
            self.__close_file()

    def cancel(self) -> None:
        """
        Cancels PMTiles writing and closes the output file.

        :returns: None
        """
        self.__writer = None
        self.__close_file()

    def __close_file(self) -> None:
        """
        Closes the PMTiles output file if it is still open.

        :returns: None
        """
        file_handle: Optional[object] = self.__file
        if file_handle is None:
            return

        file_handle.close()
        self.__file = None
