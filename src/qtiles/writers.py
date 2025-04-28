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

import sqlite3
import zipfile
import json

from qgis.core import QgsRectangle
from qgis.PyQt.QtCore import (
    QBuffer,
    QByteArray,
    QFileInfo,
    QIODevice,
    QTemporaryFile,
    QDir,
)
from qgis.PyQt.QtGui import QImage

from .mbutils import *
from qtiles.tile import Tile


class DirectoryWriter:
    """
    Handles writing tiles to a directory structure.

    This class organizes tiles into a folder hierarchy based on zoom levels
    and coordinates. It ensures that the directory structure is created
    dynamically as tiles are written.
    """

    def __init__(self, output_path: QFileInfo, root_dir: str) -> None:
        """
        Initializes the DirectoryWriter with the output path and root directory.

        :param output_path: The base directory where tiles will be saved.
        :param root_dir: The root directory name for the tile structure.
        """
        self.output = output_path
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
        path = "%s/%s/%s" % (self.root_dir, tile.z, tile.x)
        dirPath = "%s/%s" % (self.output.absoluteFilePath(), path)
        QDir().mkpath(dirPath)
        image.save(
            "%s/%s.%s" % (dirPath, tile.y, format.lower()), format, quality
        )

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

    def __init__(self, output_path: QFileInfo, root_dir: str) -> None:
        """
        Initializes the ZipWriter with the output path and root directory.

        :param output_path: The path to the ZIP file to be created.
        :param root_dir: The root directory name for the tile structure.
        """
        self.output = output_path
        self.root_dir = root_dir

        self.zipFile = zipfile.ZipFile(
            str(self.output.absoluteFilePath()), "w", allowZip64=True
        )
        self.tempFile = QTemporaryFile()
        self.tempFile.setAutoRemove(False)
        self.tempFile.open(QIODevice.OpenModeFlag.WriteOnly)
        self.tempFileName = self.tempFile.fileName()
        self.tempFile.close()

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
        path = "%s/%s/%s" % (self.root_dir, tile.z, tile.x)

        image.save(self.tempFileName, format, quality)
        tilePath = "%s/%s.%s" % (path, tile.y, format.lower())
        self.zipFile.write(
            bytes(str(self.tempFileName).encode("utf8")), tilePath
        )

    def finalize(self) -> None:
        """
        Finalizes the writing process.

        This method closes the ZIP file and removes temporary files used
        during the writing process.
        """
        self.tempFile.close()
        self.tempFile.remove()
        self.zipFile.close()


class NGMArchiveWriter(ZipWriter):
    """
    Specialized writer for creating NGM archives.

    This class extends ZipWriter to include metadata specific to NGM
    archives, such as tile levels and renderer properties.
    """

    def __init__(self, output_path: QFileInfo, root_dir: str) -> None:
        """
        Initializes the NGMArchiveWriter with the output path and root directory.

        :param output_path: The path to the NGM archive to be created.
        :param root_dir: The root directory name for the tile structure.
        """
        ZipWriter.__init__(self, output_path, "Mapnik")
        self.levels = {}
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
        ZipWriter.writeTile(self, tile, image, format, quality)
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

        tempFile = QTemporaryFile()
        tempFile.setAutoRemove(False)
        tempFile.open(QIODevice.OpenModeFlag.WriteOnly)
        tempFile.write(bytes(json.dumps(archive_info).encode("utf8")))
        tempFileName = tempFile.fileName()
        tempFile.close()

        self.zipFile.write(tempFileName, "%s.json" % self.root_dir)

        ZipWriter.finalize(self)


class MBTilesWriter:
    """
    Handles writing tiles to an MBTiles SQLite database.

    This class stores generated tiles inside an MBTiles database,
    including associated metadata such as zoom levels, extent, and compression information.
    """

    def __init__(
        self,
        output_path: QFileInfo,
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
        self.output = output_path
        self.root_dir = root_dir
        self.compression = compression
        s = (
            str(extent.xMinimum())
            + ","
            + str(extent.yMinimum())
            + ","
            + str(extent.xMaximum())
            + ","
            + str(extent.yMaximum())
        )
        self.connection = mbtiles_connect(str(self.output.absoluteFilePath()))
        self.cursor = self.connection.cursor()
        optimize_connection(self.cursor)
        mbtiles_setup(self.cursor)
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
            ("bounds", s),
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
        optimize_database(self.connection)
        self.connection.commit()
        if self.compression:
            # start compression
            compression_prepare(self.cursor, self.connection)
            self.cursor.execute("select count(zoom_level) from tiles")
            res = self.cursor.fetchone()
            total_tiles = res[0]
            compression_do(self.cursor, self.connection, total_tiles)
            compression_finalize(self.cursor)
            optimize_database(self.connection)
            self.connection.commit()
            # end compression
        self.connection.close()
        self.cursor = None
