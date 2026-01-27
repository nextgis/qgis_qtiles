import zipfile
from pathlib import Path

from qgis.PyQt.QtCore import QIODevice, QTemporaryFile
from qgis.PyQt.QtGui import QImage

from qtiles.tile import Tile
from qtiles.writers.abstract_tiles_writer import AbstractTilesWriter


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
        self.__temp_file.open(QIODevice.OpenModeFlag.WriteOnly)
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

        image.save(self.__temp_file_name, image_format, quality)
        self.__zip_file.write(self.__temp_file_name, arcname=tile_path)

    def finalize(self) -> None:
        """
        Finalizes the ZIP archive and releases temporary resources.

        :returns: None
        """
        self.__zip_file.close()
        self.__temp_file.remove()
