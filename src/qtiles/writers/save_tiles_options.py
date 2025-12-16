from pathlib import Path
from typing import Optional

from qgis.core import QgsMapSettings, QgsRectangle


class SaveTilesOptions:
    """
    Container for configuration options related to saving auxiliary
    artifacts such as metadata, overview images, and viewers.
    """

    def __init__(
        self,
        output_path: Path,
        root_dir: str,
        image_format: str,
        quality: int,
        min_zoom: int,
        max_zoom: int,
        extent: QgsRectangle,
        overview_map_settings: QgsMapSettings,
        compression: bool = False,
        tms_convention: bool = False,
        write_mapurl: bool = False,
        write_overview: bool = False,
        write_viewer: bool = False,
        write_json_metadata: bool = False,
    ) -> None:
        """
        :param output_path: Destination path or file for the writer.
        :type output_path: Path
        :param root_dir: Tile set name.
        :type root_dir: str
        :param image_format: Image format string.
        :type image_format: str
        :param quality: Image quality (0–100).
        :type quality: int
        :param min_zoom: Minimum zoom level.
        :type min_zoom: int
        :param max_zoom: Maximum zoom level.
        :type max_zoom: int
        :param extent: Geographic extent.
        :type extent: QgsRectangle
        :param overview_map_settings: Map settings to use for overview rendering.
        :type overview_map_settings: QgsMapSettings
        :param compression: Enable compression.
        :type compression: bool
        :param tms_convention: Whether tile indexing uses TMS (DIR writer only).
        :type tms_convention: bool
        :param write_mapurl: Whether to generate .mapurl file (DIR only).
        :type write_mapurl: bool
        :param write_overview: Whether to generate overview image.
        :type write_overview: bool
        :param write_viewer: Whether to generate Leaflet viewer (DIR only).
        :type write_viewer: bool
        :param write_json_metadata: Whether to write JSON metadata file.
        :type write_json_metadata: bool
        """
        self.output_path = output_path
        self.root_dir = root_dir
        self.image_format = image_format
        self.quality = quality
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.extent = extent
        self.overview_map_settings = overview_map_settings
        self.compression = compression
        self.tms_convention = tms_convention
        self.write_mapurl = write_mapurl
        self.write_overview = write_overview
        self.write_viewer = write_viewer
        self.write_json_metadata = write_json_metadata
