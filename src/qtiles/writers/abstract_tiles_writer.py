from abc import ABC, abstractmethod

from qgis.PyQt.QtGui import QImage

from qtiles.tile import Tile


class AbstractTilesWriter(ABC):
    """
    Abstract base class for all tile writers.
    """

    @abstractmethod
    def write_tile(
        self,
        tile: Tile,
        image: QImage,
        image_format: str,
        quality: int,
    ) -> None:
        """
        Writes a single tile to the output storage.

        :param tile: Tile descriptor containing z, x, y coordinates.
        :type tile: Tile
        :param image: Rendered tile image.
        :type image: QImage
        :param image_format: The image format (e.g., 'PNG', 'JPEG') to use for saving.
        :type image_format: str
        :param quality: The image quality (0–100)
        :type quality: int

        :returns: None.
        """
        raise NotImplementedError

    @abstractmethod
    def finalize(self) -> None:
        """
        Finalizes the writer after all tiles are written.

        This may include closing file handles, writing metadata,
        flushing buffers, or performing format-specific cleanup.

        :returns: None.
        """
        raise NotImplementedError
