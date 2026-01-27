import json
import zipfile
from pathlib import Path
from typing import Dict, List

from qgis.PyQt.QtCore import QIODevice, QTemporaryFile
from qgis.PyQt.QtGui import QImage

from qtiles.tile import Tile
from qtiles.writers.abstract_tiles_writer import AbstractTilesWriter


class NGMArchiveTilesWriter(AbstractTilesWriter):
    """
    Writes tiles into an NGM archive.

    The archive is a ZIP file containing a Mapnik tile directory
    and a JSON metadata file describing tile levels and renderer
    properties.
    """

    def __init__(self, *, output_path: Path, root_dir: str) -> None:
        """
        Initializes the NGM archive writer.

        :param output_path: Path to the NGM archive file.
        :type output_path: Path
        :param root_dir: tile set name stored in metadata.
        :type root_dir: str
        """
        self.__output_path = output_path
        self.__root_dir = root_dir

        self.__zip_file = zipfile.ZipFile(
            str(self.__output_path),
            mode="w",
            allowZip64=True,
        )

        self.__temp_file = QTemporaryFile()
        self.__temp_file.setAutoRemove(False)
        self.__temp_file.open(QIODevice.OpenModeFlag.WriteOnly)
        self.__temp_file_name = self.__temp_file.fileName()
        self.__temp_file.close()

        self.__levels: Dict[int, Dict[str, List[int]]] = {}

    def write_tile(
        self,
        tile: Tile,
        image: QImage,
        image_format: str,
        quality: int,
    ) -> None:
        """
        Writes a single tile into the NGM archive and records
        its coordinates for metadata generation.

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
        tile_path = (
            f"{self.__root_dir}/"
            f"{tile.z}/"
            f"{tile.x}/"
            f"{tile.y}.{image_format.lower()}"
        )

        image.save(self.__temp_file_name, image_format, quality)
        self.__zip_file.write(self.__temp_file_name, arcname=tile_path)

        level = self.__levels.get(tile.z, {"x": [], "y": []})
        level["x"].append(tile.x)
        level["y"].append(tile.y)

    def finalize(self) -> None:
        """
        Finalizes the NGM archive by writing metadata and
        closing all resources.

        :returns: None
        """
        if self.__levels:
            self.__write_metadata()

        try:
            self.__zip_file.close()
        finally:
            self.__temp_file.remove()

    def __write_metadata(self) -> None:
        """
        Writes the NGM metadata JSON into the archive.

        :returns: None
        """
        archive_info = {
            "cache_size_multiply": 0,
            "levels": [],
            "max_level": max(self.__levels.keys()),
            "min_level": min(self.__levels.keys()),
            "name": self.__root_dir,
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

        for level, coords in self.__levels.items():
            archive_info["levels"].append(
                {
                    "level": level,
                    "bbox_maxx": max(coords["x"]),
                    "bbox_maxy": max(coords["y"]),
                    "bbox_minx": min(coords["x"]),
                    "bbox_miny": min(coords["y"]),
                }
            )

        json_bytes = json.dumps(archive_info).encode("utf-8")
        json_name = f"{self.__root_dir}.json"
        self.__zip_file.writestr(json_name, json_bytes)
