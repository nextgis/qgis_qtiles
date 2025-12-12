# -*- coding: utf-8 -*-

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
import sqlite3
import zipfile
from pathlib import Path
from typing import Dict, List

from qgis.core import QgsRectangle
from qgis.PyQt.QtCore import (
    QBuffer,
    QByteArray,
    QIODevice,
    QTemporaryFile,
)
from qgis.PyQt.QtGui import QImage

from qtiles.external.mbutil import mbutils
from qtiles.tile import Tile


class DirectoryWriter:
    """
    Handles writing tiles to a directory structure.

    This class organizes tiles into a folder hierarchy based on zoom levels
    and coordinates. It ensures that the directory structure is created
    dynamically as tiles are written.
    """

    def __init__(self, output_path: Path, root_dir: str) -> None:
        """
        Initializes the DirectoryWriter with the output path and root directory.

        :param output_path: The base directory where tiles will be saved.
        :param root_dir: The root directory name for the tile structure.
        """
        self.output_path = output_path
        self.root_dir = root_dir

    def writeTile(
        self, tile: Tile, image: QImage, format: str, quality: int
    ) -> None:
        """
        Saves a single image tile to the appropriate directory based on zoom level and coordinates.

        The method creates the necessary directory structure if it doesn't already exist,
        and writes the tile image to disk using the specified format and quality.

        :param tile: A Tile object containing the zoom level (z), x, and y coordinates.
        :param image: The QImage representing the tile image to be saved.
        :param format: The image format (e.g., 'PNG', 'JPEG') to use for saving.
        :param quality: The image quality (0–100), where higher values indicate better quality.
        """
        dir_path = self.output_path / self.root_dir / str(tile.z) / str(tile.x)
        dir_path.mkdir(parents=True, exist_ok=True)

        tile_file = dir_path / f"{tile.y}.{format.lower()}"
        image.save(str(tile_file), format, quality)

    def finalize(self) -> None:
        """
        Finalizes the writing process.
        """
        pass


class ZipWriter:
    """
    Handles writing tiles to a ZIP archive.

    This class compresses tiles into a ZIP file, maintaining a folder
    structure within the archive based on zoom levels and coordinates.
    """

    def __init__(self, output_path: Path, root_dir: str) -> None:
        """
        Initializes the ZipWriter with the output path and root directory.

        :param output_path: The path to the ZIP file to be created.
        :param root_dir: The root directory name for the tile structure.
        """
        self.output_path = output_path
        self.root_dir = root_dir

        self.zip_file = zipfile.ZipFile(
            str(self.output_path), "w", allowZip64=True
        )
        self.temp_file = QTemporaryFile()
        self.temp_file.setAutoRemove(False)
        self.temp_file.open(QIODevice.OpenModeFlag.WriteOnly)
        self.temp_file_name = self.temp_file.fileName()
        self.temp_file.close()

    def writeTile(
        self, tile: Tile, image: QImage, format: str, quality: int
    ) -> None:
        """
        Saves a tile image to the ZIP archive.

        :param tile: The tile object containing zoom level and coordinates.
        :param image: The image to save.
        :param format: The image format (e.g., PNG, JPG).
        :param quality: The quality of the saved image.
        """
        tile_path = (
            f"{self.root_dir}/{tile.z}/{tile.x}/{tile.y}.{format.lower()}"
        )

        image.save(self.temp_file_name, format, quality)

        self.zip_file.write(self.temp_file_name, arcname=tile_path)

    def finalize(self) -> None:
        """
        Finalizes the writing process.

        This method closes the ZIP file and removes temporary files used
        during the writing process.
        """
        self.temp_file.close()
        self.temp_file.remove()
        self.zip_file.close()


class NGMArchiveWriter(ZipWriter):
    """
    Specialized writer for creating NGM archives.

    This class extends ZipWriter to include metadata specific to NGM
    archives, such as tile levels and renderer properties.
    """

    def __init__(self, output_path: Path, root_dir: str) -> None:
        """
        Initializes the NGMArchiveWriter with the output path and root directory.

        :param output_path: The path to the NGM archive to be created.
        :param root_dir: The root directory name for the tile structure.
        """
        super().__init__(output_path, "Mapnik")
        self.levels: Dict[int, Dict[str, List[int]]] = {}
        self.__layer_name = root_dir

    def writeTile(
        self, tile: Tile, image: QImage, format: str, quality: int
    ) -> None:
        """
        Saves a tile image to the NGM archive.

        :param tile: The tile object containing zoom level and coordinates.
        :param image: The image to save.
        :param format: The image format (e.g., PNG, JPG).
        :param quality: The quality of the saved image.
        """
        super().writeTile(tile, image, format, quality)
        level = self.levels.get(tile.z, {"x": [], "y": []})
        level["x"].append(tile.x)
        level["y"].append(tile.y)

        self.levels[tile.z] = level

    def finalize(self) -> None:
        """
        Finalizes the writing process by adding metadata to the archive.

        This method generates a JSON file containing metadata about the
        tile levels and renderer properties, which is then added to the
        archive.
        """
        archive_info = {
            "cache_size_multiply": 0,
            "levels": [],
            "max_level": max(self.levels.keys()),
            "min_level": min(self.levels.keys()),
            "name": self.__layer_name,
            "renderer_properties": {
                "alpha": 255,
                "antialias": True,
                "brightness": 0,
                "contrast": 1,
                "dither": True,
                "filterbitmap": True,
                "greyscale": False,
                "type": "tms_renderer",
            },
            "tms_type": 2,
            "type": 32,
            "visible": True,
        }

        for level, coords in list(self.levels.items()):
            level_json = {
                "level": level,
                "bbox_maxx": max(coords["x"]),
                "bbox_maxy": max(coords["y"]),
                "bbox_minx": min(coords["x"]),
                "bbox_miny": min(coords["y"]),
            }

            archive_info["levels"].append(level_json)

        json_bytes = json.dumps(archive_info).encode("utf-8")
        json_name = f"{self.root_dir}.json"
        self.zip_file.writestr(json_name, json_bytes)

        super().finalize()


class MBTilesWriter:
    """
    Handles writing tiles to an MBTiles SQLite database.

    This class stores generated tiles inside an MBTiles database,
    including associated metadata such as zoom levels, extent, and compression information.
    """

    def __init__(
        self,
        output_path: Path,
        root_dir: str,
        formatext: str,
        min_zoom: int,
        max_zoom: int,
        extent: QgsRectangle,
        compression: bool,
    ) -> None:
        """
        Initializes the MBTilesWriter with output parameters and database setup.

        :param output_path: The path to the MBTiles file to be created.
        :param root_dir: The name of the root directory or layer (used in metadata).
        :param formatext: The image format (e.g., PNG, JPG) to store tiles.
        :param min_zoom: The minimum zoom level.
        :param max_zoom: The maximum zoom level.
        :param extent: The geographic extent (bounding box) of the tiles.
        :param compression: Whether to apply tile data compression after writing.
        """
        self.output_path = output_path
        self.root_dir = root_dir

        self.compression = compression
        bounds = f"{extent.xMinimum()},{extent.yMinimum()},{extent.xMaximum()},{extent.yMaximum()}"
        self.connection = mbutils.mbtiles_connect(
            str(self.output_path), silent=False
        )
        self.cursor = self.connection.cursor()
        mbutils.optimize_connection(self.cursor)
        mbutils.mbtiles_setup(self.cursor)
        self.cursor.execute(
            """INSERT INTO metadata(name, value) VALUES (?, ?);""",
            ("name", self.root_dir),
        )
        self.cursor.execute(
            """INSERT INTO metadata(name, value) VALUES (?, ?);""",
            ("description", "Created with QTiles"),
        )
        self.cursor.execute(
            """INSERT INTO metadata(name, value) VALUES (?, ?);""",
            ("format", formatext.lower()),
        )
        self.cursor.execute(
            """INSERT INTO metadata(name, value) VALUES (?, ?);""",
            ("minZoom", str(min_zoom)),
        )
        self.cursor.execute(
            """INSERT INTO metadata(name, value) VALUES (?, ?);""",
            ("maxZoom", str(max_zoom)),
        )
        self.cursor.execute(
            """INSERT INTO metadata(name, value) VALUES (?, ?);""",
            ("type", "baselayer"),
        )
        self.cursor.execute(
            """INSERT INTO metadata(name, value) VALUES (?, ?);""",
            ("version", "1.1"),
        )
        self.cursor.execute(
            """INSERT INTO metadata(name, value) VALUES (?, ?);""",
            ("bounds", bounds),
        )
        self.connection.commit()

    def writeTile(
        self, tile: Tile, image: QImage, format: str, quality: int
    ) -> None:
        """
        Inserts a single tile into the MBTiles database.

        :param tile: The tile object containing zoom level and coordinates.
        :param image: The image data to store.
        :param format: The image format (e.g., PNG, JPG).
        :param quality: The quality level for the saved image.
        """
        data = QByteArray()
        buff = QBuffer(data)
        image.save(buff, format, quality)

        self.cursor.execute(
            """INSERT INTO tiles(zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?);""",
            (tile.z, tile.x, tile.y, sqlite3.Binary(buff.data())),
        )
        buff.close()

    def finalize(self) -> None:
        """
        Finalizes the writing process.

        This method optimizes the database, optionally compresses tile data,
        and properly closes the database connection.
        """
        self.connection.commit()
        if self.compression:
            # start compression
            mbutils.compression_prepare(self.cursor, self.connection)
            self.cursor.execute("select count(zoom_level) from tiles")
            res = self.cursor.fetchone()
            total_tiles = res[0]
            mbutils.compression_do(
                self.cursor, self.connection, total_tiles, silent=False
            )
            mbutils.compression_finalize(
                self.cursor, self.connection, silent=False
            )
            self.connection.commit()
            # end compression

        mbutils.optimize_database(self.connection, silent=False)
        self.connection.close()
        self.cursor = None
