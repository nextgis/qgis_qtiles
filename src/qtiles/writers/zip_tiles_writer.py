import zipfile
from pathlib import Path
from typing import Optional

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QIODevice, QTemporaryFile
from qgis.PyQt.QtGui import QImage

from qtiles.tile import Tile
from qtiles.writers.abstract_tiles_writer import AbstractTilesWriter
from qtiles.writers.utils import ensure_operation_succeeded


class ZipTilesWriter(AbstractTilesWriter):
    """
    Writes tiles into a ZIP archive.

    Tiles are stored inside the archive using a directory structure
    based on zoom level and tile coordinates:
    <root_dir>/<z>/<x>/<y>.<format>.
    """

    def __init__(self, *, output_path: Path, root_dir: str) -> None:
        """
        Initializes the ZIP tiles writer.

        :param output_path: Path to the ZIP file to be created.
        :type output_path: Path
        :param root_dir: Root directory name inside the ZIP archive.
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
        # fmt: off
        ensure_operation_succeeded(
            self.__temp_file.open(QIODevice.OpenModeFlag.WriteOnly),
            log_message="Failed to create temporary file for ZIP tiles",
            user_message=QgsApplication.translate(
                "QTiles", "Failed to prepare tile archive output."
            ),
            detail=QgsApplication.translate(
                "QTiles",
                "Could not create a temporary file used for ZIP export."
            ),
        )
        # fmt: on
        self.__temp_file_name = self.__temp_file.fileName()
        self.__temp_file.close()

    def write_tile(
        self,
        tile: Tile,
        image: QImage,
        image_format: str,
        quality: int,
    ) -> None:
        """
        Writes a single tile image into the ZIP archive.

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

        # fmt: off
        ensure_operation_succeeded(
            image.save(self.__temp_file_name, image_format, quality),
            log_message="Failed to encode tile image for ZIP archive",
            user_message=QgsApplication.translate(
                "QTiles", "Failed to write one of the generated tiles."
            ),
            detail=QgsApplication.translate(
                "QTiles",
                "Tile {z}/{x}/{y} could not be encoded before writing "
                "to ZIP archive."
            ).format(
                z=tile.z,
                x=tile.x,
                y=tile.y,
            ),
        )
        # fmt: on
        self.__zip_file.write(self.__temp_file_name, arcname=tile_path)

    def finalize(self) -> None:
        """
        Finalizes the ZIP archive and releases temporary resources.

        :returns: None
        """
        self.__zip_file.close()
        self.__remove_temporary_file()

    def cancel(self) -> None:
        """
        Cancels ZIP archive writing and releases temporary resources.

        :returns: None
        """
        if self.__zip_file is not None:
            self.__zip_file.close()
            self.__zip_file = None

        self.__remove_temporary_file()

    def __remove_temporary_file(self) -> None:
        """
        Removes the temporary file used for tile encoding.

        :returns: None
        """
        temp_file: Optional[QTemporaryFile] = self.__temp_file
        if temp_file is None:
            return

        temp_file.remove()
        self.__temp_file = None
