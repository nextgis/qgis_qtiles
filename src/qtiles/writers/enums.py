from enum import Enum
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication


class TilesWriterMode(Enum):
    """
    Enumeration of supported tile writer modes.
    """

    DIR = "DIR"
    ZIP = "ZIP"
    NGM = "NGM"
    MBTILES = "MBTILES"
    PMTILES = "PMTILES"

    @staticmethod
    def from_output_path(path: Path) -> "TilesWriterMode":
        """
        Detects writer mode from output path.

        :param path: Output path provided by the user.
        :type path: Path

        :returns: Detected tile writer mode.
        :rtype: TilesWriterMode
        """
        if path.is_dir():
            return TilesWriterMode.DIR

        suffix = path.suffix.lower()
        if suffix == ".zip":
            return TilesWriterMode.ZIP
        if suffix == ".ngrc":
            return TilesWriterMode.NGM
        if suffix == ".mbtiles":
            return TilesWriterMode.MBTILES
        if suffix == ".pmtiles":
            return TilesWriterMode.PMTILES

        raise ValueError(
            QCoreApplication.translate(
                "TilesWritersMode", "Unsupported writer mode: {}"
            ).format(suffix)
        )
