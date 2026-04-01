from pathlib import Path

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QImage

from qtiles.tile import Tile
from qtiles.writers.abstract_tiles_writer import AbstractTilesWriter
from qtiles.writers.utils import ensure_operation_succeeded


class DirectoryTilesWriter(AbstractTilesWriter):
    """
    Writes tiles to a directory structure on disk.
    """

    def __init__(self, *, output_path: Path, root_dir: str) -> None:
        """
        Initializes the DirectoryWriter with the output path and root directory.

        :param output_path: The base directory where tiles will be saved.
        :param root_dir: The root directory name for the tile structure.
        """
        self.__output_path = output_path
        self.__root_dir = root_dir

    def write_tile(
        self,
        tile: Tile,
        image: QImage,
        image_format: str,
        quality: int,
    ) -> None:
        """
        Writes a single tile image to the appropriate directory.

        :param tile: Tile descriptor.
        :type tile: Tile
        :param image: The tile image to save.
        :type image: QImage
        :param image_format: The image format (e.g., 'PNG', 'JPEG') to use for saving.
        :type image_format: str
        :param quality: The image quality (0–100)
        :type quality: int

        :returns: None
        """

        dir_path = (
            self.__output_path / self.__root_dir / str(tile.z) / str(tile.x)
        )
        dir_path.mkdir(parents=True, exist_ok=True)

        tile_file = dir_path / f"{tile.y}.{image_format.lower()}"
        # fmt: off
        ensure_operation_succeeded(
            image.save(str(tile_file), image_format, quality),
            log_message=f"Failed to save tile to disk: {tile_file}",
            user_message=QgsApplication.translate(
                "QTiles", "Failed to write one of the generated tiles."
            ),
            detail=QgsApplication.translate(
                "QTiles",
                "Tile {z}/{x}/{y} could not be saved to '{path}'."
            ).format(
                z=tile.z,
                x=tile.x,
                y=tile.y,
                path=tile_file,
            ),
        )
        # fmt: on

    def finalize(self) -> None:
        """
        Finalizes tile writing (e.g., closing files, archiving).

        There is no need to do anything for the directory writer.
        """
        pass
