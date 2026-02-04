from enum import Enum
from typing import Optional

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

    @classmethod
    def tr(cls, text: str) -> str:
        """
        Translate text in TilesWriterMode context.

        :param text: Source text.

        :returns: Translated text.
        """
        return QCoreApplication.translate(cls.__name__, text)

    @property
    def file_extension(self) -> Optional[str]:
        """
        Return the file extension associated with the writer mode.

        :returns: File extension including the leading dot
        """
        file_extension_mapping = {
            TilesWriterMode.ZIP: ".zip",
            TilesWriterMode.MBTILES: ".mbtiles",
            TilesWriterMode.PMTILES: ".pmtiles",
            TilesWriterMode.NGM: ".ngrc",
        }

        return file_extension_mapping.get(self)

    @property
    def is_directory(self) -> bool:
        """
        Return whether the writer mode outputs to a directory.

        :returns: ``True`` if the output target is a directory.
        """
        return self is TilesWriterMode.DIR

    @property
    def file_dialog_filter(self) -> Optional[str]:
        """
        Return QFileDialog filter string for the writer mode.

        :returns: File dialog filter or ``None`` for directory mode.
        """
        file_dialog_filter_mapping = {
            TilesWriterMode.ZIP: self.tr("ZIP archives (*.zip *.ZIP)"),
            TilesWriterMode.MBTILES: self.tr(
                "MBTiles databases (*.mbtiles *.MBTILES)"
            ),
            TilesWriterMode.PMTILES: self.tr(
                "PMTiles archives (*.pmtiles *.PMTILES)"
            ),
            TilesWriterMode.NGM: self.tr("NextGIS Mobile archive (*.ngrc)"),
        }

        return file_dialog_filter_mapping.get(self)
