import sqlite3
from pathlib import Path
from typing import Optional

from qgis.core import QgsApplication, QgsRectangle
from qgis.PyQt.QtCore import QBuffer, QByteArray
from qgis.PyQt.QtGui import QImage

from qtiles.external.mbutil import mbutils
from qtiles.tile import Tile
from qtiles.writers.abstract_tiles_writer import AbstractTilesWriter
from qtiles.writers.utils import ensure_operation_succeeded


class MBTilesWriter(AbstractTilesWriter):
    """
    Writes tiles into an MBTiles SQLite database.

    This writer stores tiles and required MBTiles metadata,
    and optionally applies tile compression on finalize.
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
        compression: bool,
    ) -> None:
        """
        Initializes the MBTiles writer and prepares database schema.

        :param output_path: Path to the MBTiles file.
        :type output_path: Path
        :param root_dir: Logical tile set name stored in metadata.
        :type root_dir: str
        :param image_format: Image format (e.g. 'PNG', 'JPEG').
        :type image_format: str
        :param min_zoom: Minimum zoom level.
        :type min_zoom: int
        :param max_zoom: Maximum zoom level.
        :type max_zoom: int
        :param extent: Geographic extent of the tileset.
        :type extent: QgsRectangle
        :param compression: Whether to apply tile compression.
        :type compression: bool
        """
        self.__compression = compression

        bounds = (
            f"{extent.xMinimum()},"
            f"{extent.yMinimum()},"
            f"{extent.xMaximum()},"
            f"{extent.yMaximum()}"
        )

        self.__connection = mbutils.mbtiles_connect(
            str(output_path),
            silent=False,
        )
        self.__cursor = self.__connection.cursor()

        mbutils.optimize_connection(self.__cursor)
        mbutils.mbtiles_setup(self.__cursor)

        self.__cursor.executemany(
            """INSERT INTO metadata(name, value) VALUES (?, ?);""",
            [
                ("name", root_dir),
                ("description", "Created with QTiles"),
                ("format", image_format.lower()),
                ("minZoom", str(min_zoom)),
                ("maxZoom", str(max_zoom)),
                ("type", "baselayer"),
                ("version", "1.1"),
                ("bounds", bounds),
            ],
        )

        self.__connection.commit()

    def write_tile(
        self,
        tile: Tile,
        image: QImage,
        image_format: str,
        quality: int,
    ) -> None:
        """
        Inserts a single tile into the MBTiles database.

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
            buffer.open(QBuffer.OpenModeFlag.WriteOnly),
            log_message="Failed to open MBTiles buffer for tile encoding",
            user_message=QgsApplication.translate(
                "QTiles", "Failed to write one of the generated tiles."
            ),
            detail=QgsApplication.translate(
                "QTiles",
                "Could not allocate an in-memory buffer for MBTiles tile "
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
            log_message="Failed to encode tile image for MBTiles",
            user_message=QgsApplication.translate(
                "QTiles", "Failed to write one of the generated tiles."
            ),
            detail=QgsApplication.translate(
                "QTiles",
                "Tile {z}/{x}/{y} could not be encoded before writing "
                "to MBTiles."
            ).format(
                z=tile.z,
                x=tile.x,
                y=tile.y,
            ),
        )
        # fmt: on

        self.__cursor.execute(
            """
            INSERT INTO tiles(
                zoom_level,
                tile_column,
                tile_row,
                tile_data
            )
            VALUES (?, ?, ?, ?);
            """,
            (
                tile.z,
                tile.x,
                tile.y,
                sqlite3.Binary(data),
            ),
        )

        buffer.close()

    def finalize(self) -> None:
        """
        Finalizes MBTiles writing.

        Commits pending changes, optionally compresses tile data,
        optimizes the database, and closes the connection.

        :returns: None
        """
        connection = self.__connection
        cursor = self.__cursor

        if connection is None or cursor is None:
            return

        try:
            connection.commit()

            if self.__compression:
                mbutils.compression_prepare(cursor, connection)

                cursor.execute("SELECT COUNT(zoom_level) FROM tiles;")
                total_tiles = cursor.fetchone()[0]

                mbutils.compression_do(
                    cursor,
                    connection,
                    total_tiles,
                    silent=False,
                )
                mbutils.compression_finalize(
                    cursor,
                    connection,
                    silent=False,
                )
                connection.commit()

            mbutils.optimize_database(connection, silent=False)
        finally:
            self.__close_resources()

    def cancel(self) -> None:
        """
        Cancels MBTiles writing and closes the database connection.

        :returns: None
        """
        self.__close_resources()

    def __close_resources(self) -> None:
        """
        Closes any open MBTiles cursor and database connection.

        :returns: None
        """
        cursor: Optional[sqlite3.Cursor] = self.__cursor
        connection: Optional[sqlite3.Connection] = self.__connection

        self.__cursor = None
        self.__connection = None

        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()
