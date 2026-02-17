import platform
from pathlib import Path
from typing import ClassVar

from qgis.core import QgsProject, QgsSettings
from qgis.PyQt.QtCore import QSettings

from qtiles.core.constants import COMPANY_NAME, PLUGIN_NAME


class QTilesSettings:
    """Centralized settings handler for the QTiles plugin."""

    KEY_LAST_OUTPUT_DIR = f"{COMPANY_NAME}/{PLUGIN_NAME}/lastOutputDir"
    KEY_TILESET_NAME = f"{COMPANY_NAME}/{PLUGIN_NAME}/tilesetName"
    KEY_TILES_WRITER_MODE = f"{COMPANY_NAME}/{PLUGIN_NAME}/tilesWriterMode"
    KEY_MIN_ZOOM = f"{COMPANY_NAME}/{PLUGIN_NAME}/minZoom"
    KEY_MAX_ZOOM = f"{COMPANY_NAME}/{PLUGIN_NAME}/maxZoom"
    KEY_TILE_SIZE = f"{COMPANY_NAME}/{PLUGIN_NAME}/tileSize"
    KEY_DPI = f"{COMPANY_NAME}/{PLUGIN_NAME}/dpi"
    KEY_TILE_OUTPUT_FORMAT = f"{COMPANY_NAME}/{PLUGIN_NAME}/tileOutputFormat"
    KEY_JPG_QUALITY = f"{COMPANY_NAME}/{PLUGIN_NAME}/jpgQuality"
    KEY_ENABLE_ANTIALIASING = (
        f"{COMPANY_NAME}/{PLUGIN_NAME}/enableAntialiasing"
    )
    KEY_TRANSPARENT_BACKGROUND = (
        f"{COMPANY_NAME}/{PLUGIN_NAME}/transparentBackground"
    )
    KEY_RENDER_OUTSIDE_TILES = (
        f"{COMPANY_NAME}/{PLUGIN_NAME}/renderOutsideTiles"
    )
    KEY_USE_TMS_CONVENTION = f"{COMPANY_NAME}/{PLUGIN_NAME}/useTmsConvention"
    KEY_USE_MBTILES_COMPRESSION = (
        f"{COMPANY_NAME}/{PLUGIN_NAME}/useMbtilesCompression"
    )
    KEY_WRITE_JSON_METADATA = f"{COMPANY_NAME}/{PLUGIN_NAME}/writeJsonMetadata"
    KEY_WRITE_OVERVIEW = f"{COMPANY_NAME}/{PLUGIN_NAME}/writeOverview"
    KEY_WRITE_MAPURL = f"{COMPANY_NAME}/{PLUGIN_NAME}/writeMapurl"
    KEY_WRITE_LEAFLET_VIEWER = (
        f"{COMPANY_NAME}/{PLUGIN_NAME}/writeLeafletViewer"
    )
    KEY_IS_DEBUG_LOGS_ENABLED = (
        f"{COMPANY_NAME}/{PLUGIN_NAME}/other/debugLogsEnabled"
    )
    KEY_DID_LAST_LAUNCH_FAIL = (
        f"{COMPANY_NAME}/{PLUGIN_NAME}/other/didLastLaunchFail"
    )

    __is_updated: ClassVar[bool] = False
    __settings: QgsSettings

    def __init__(self) -> None:
        self.__settings = QgsSettings()
        self.__update_settings()

    @property
    def last_output_dir(self) -> str:
        """Get the last output directory used by the plugin."""
        last_output_dir = self.__settings.value(
            self.KEY_LAST_OUTPUT_DIR, defaultValue=str(Path.home()), type=str
        )
        return last_output_dir

    @last_output_dir.setter
    def last_output_dir(self, value: str) -> None:
        self.__settings.setValue(self.KEY_LAST_OUTPUT_DIR, value)

    @property
    def tileset_name(self) -> str:
        """Get the current tileset name.

        Priority:
        1. Explicitly saved setting
        2. Current QGIS project name (if exists)
        3. Fallback default ("Mapnik")
        """
        value = self.__settings.value(
            self.KEY_TILESET_NAME,
            defaultValue=None,
            type=str,
        )

        if value:
            return value

        project_name = QgsProject.instance().baseName()
        if project_name:
            return project_name

        return "Mapnik"

    @tileset_name.setter
    def tileset_name(self, value: str) -> None:
        self.__settings.setValue(self.KEY_TILESET_NAME, value)

    @property
    def tiles_writer_mode(self) -> int:
        """Tiles writer mode combobox index."""
        return self.__settings.value(
            self.KEY_TILES_WRITER_MODE,
            defaultValue=0,
            type=int,
        )

    @tiles_writer_mode.setter
    def tiles_writer_mode(self, value: int) -> None:
        self.__settings.setValue(self.KEY_TILES_WRITER_MODE, value)

    @property
    def min_zoom(self) -> int:
        """Minimum zoom level."""
        return self.__settings.value(
            self.KEY_MIN_ZOOM, defaultValue=0, type=int
        )

    @min_zoom.setter
    def min_zoom(self, value: int) -> None:
        self.__settings.setValue(self.KEY_MIN_ZOOM, value)

    @property
    def max_zoom(self) -> int:
        """Maximum zoom level."""
        return self.__settings.value(
            self.KEY_MAX_ZOOM, defaultValue=18, type=int
        )

    @max_zoom.setter
    def max_zoom(self, value: int) -> None:
        self.__settings.setValue(self.KEY_MAX_ZOOM, value)

    @property
    def tile_size(self) -> int:
        """Tile size in pixels."""
        return self.__settings.value(
            self.KEY_TILE_SIZE, defaultValue=256, type=int
        )

    @tile_size.setter
    def tile_size(self, value: int) -> None:
        self.__settings.setValue(self.KEY_TILE_SIZE, value)

    @property
    def dpi(self) -> int:
        """Output DPI for tiles."""
        return self.__settings.value(self.KEY_DPI, defaultValue=96, type=int)

    @dpi.setter
    def dpi(self, value: int) -> None:
        self.__settings.setValue(self.KEY_DPI, value)

    @property
    def tile_output_format(self) -> int:
        """Output format index."""
        return self.__settings.value(
            self.KEY_TILE_OUTPUT_FORMAT, defaultValue=0, type=int
        )

    @tile_output_format.setter
    def tile_output_format(self, value: int) -> None:
        self.__settings.setValue(self.KEY_TILE_OUTPUT_FORMAT, value)

    @property
    def jpg_quality(self) -> int:
        """JPEG quality (0-100)."""
        return self.__settings.value(
            self.KEY_JPG_QUALITY, defaultValue=70, type=int
        )

    @jpg_quality.setter
    def jpg_quality(self, value: int) -> None:
        self.__settings.setValue(self.KEY_JPG_QUALITY, value)

    @property
    def enable_antialiasing(self) -> bool:
        """Render lines with antialiasing."""
        return self.__settings.value(
            self.KEY_ENABLE_ANTIALIASING, defaultValue=False, type=bool
        )

    @enable_antialiasing.setter
    def enable_antialiasing(self, value: bool) -> None:
        self.__settings.setValue(self.KEY_ENABLE_ANTIALIASING, value)

    @property
    def transparent_background(self) -> bool:
        """Render tiles with transparent background."""
        return self.__settings.value(
            self.KEY_TRANSPARENT_BACKGROUND, defaultValue=True, type=bool
        )

    @transparent_background.setter
    def transparent_background(self, value: bool) -> None:
        self.__settings.setValue(self.KEY_TRANSPARENT_BACKGROUND, value)

    @property
    def render_outside_tiles(self) -> bool:
        """Render all tiles within target extent, even if empty."""
        return self.__settings.value(
            self.KEY_RENDER_OUTSIDE_TILES, defaultValue=True, type=bool
        )

    @render_outside_tiles.setter
    def render_outside_tiles(self, value: bool) -> None:
        self.__settings.setValue(self.KEY_RENDER_OUTSIDE_TILES, value)

    @property
    def use_tms_convention(self) -> bool:
        """Use TMS Y-axis convention."""
        return self.__settings.value(
            self.KEY_USE_TMS_CONVENTION, defaultValue=False, type=bool
        )

    @use_tms_convention.setter
    def use_tms_convention(self, value: bool) -> None:
        self.__settings.setValue(self.KEY_USE_TMS_CONVENTION, value)

    @property
    def use_mbtiles_compression(self) -> bool:
        """Enable MBTiles compression."""
        return self.__settings.value(
            self.KEY_USE_MBTILES_COMPRESSION, defaultValue=False, type=bool
        )

    @use_mbtiles_compression.setter
    def use_mbtiles_compression(self, value: bool) -> None:
        self.__settings.setValue(self.KEY_USE_MBTILES_COMPRESSION, value)

    @property
    def write_json_metadata(self) -> bool:
        """Write JSON metadata file."""
        return self.__settings.value(
            self.KEY_WRITE_JSON_METADATA, defaultValue=False, type=bool
        )

    @write_json_metadata.setter
    def write_json_metadata(self, value: bool) -> None:
        self.__settings.setValue(self.KEY_WRITE_JSON_METADATA, value)

    @property
    def write_overview(self) -> bool:
        """Write overview image."""
        return self.__settings.value(
            self.KEY_WRITE_OVERVIEW, defaultValue=False, type=bool
        )

    @write_overview.setter
    def write_overview(self, value: bool) -> None:
        self.__settings.setValue(self.KEY_WRITE_OVERVIEW, value)

    @property
    def write_mapurl(self) -> bool:
        """Write MapURL file."""
        return self.__settings.value(
            self.KEY_WRITE_MAPURL, defaultValue=False, type=bool
        )

    @write_mapurl.setter
    def write_mapurl(self, value: bool) -> None:
        self.__settings.setValue(self.KEY_WRITE_MAPURL, value)

    @property
    def write_leaflet_viewer(self) -> bool:
        """Write Leaflet HTML viewer."""
        return self.__settings.value(
            self.KEY_WRITE_LEAFLET_VIEWER, defaultValue=False, type=bool
        )

    @write_leaflet_viewer.setter
    def write_leaflet_viewer(self, value: bool) -> None:
        self.__settings.setValue(self.KEY_WRITE_LEAFLET_VIEWER, value)

    @property
    def is_debug_logs_enabled(self) -> bool:
        """Check if debug logs are enabled."""
        return self.__settings.value(
            self.KEY_IS_DEBUG_LOGS_ENABLED,
            defaultValue=True,
            type=bool,
        )

    @is_debug_logs_enabled.setter
    def is_debug_logs_enabled(self, value: bool) -> None:
        self.__settings.setValue(self.KEY_IS_DEBUG_LOGS_ENABLED, value)

    @property
    def did_last_launch_fail(self) -> bool:
        """Checks whether the last plugin launch failed."""
        return self.__settings.value(
            self.KEY_DID_LAST_LAUNCH_FAIL,
            defaultValue=False,
            type=bool,
        )

    @did_last_launch_fail.setter
    def did_last_launch_fail(self, value: bool) -> None:
        self.__settings.setValue(self.KEY_DID_LAST_LAUNCH_FAIL, value)

    @classmethod
    def __update_settings(cls) -> None:
        """Perform one-time migration from old QSettings storage."""
        if cls.__is_updated:
            return

        qgs_settings = QgsSettings()
        cls.__migrate_from_qsettings(qgs_settings)

        cls.__is_updated = True

    @classmethod
    def __migrate_from_qsettings(cls, qgs_settings: QgsSettings) -> None:
        """Migrate from QSettings to QgsSettings"""
        old_settings = QSettings(COMPANY_NAME, PLUGIN_NAME)
        if platform.system() != "Darwin" and len(old_settings.allKeys()) == 0:
            return

        settings_key_map = {
            "rootDir": cls.KEY_TILESET_NAME,
            "minZoom": cls.KEY_MIN_ZOOM,
            "maxZoom": cls.KEY_MAX_ZOOM,
            "tileWidth": cls.KEY_TILE_SIZE,
            "format": cls.KEY_TILE_OUTPUT_FORMAT,
            "quality": cls.KEY_JPG_QUALITY,
            "enable_antialiasing": cls.KEY_ENABLE_ANTIALIASING,
            "renderOutsideTiles": cls.KEY_RENDER_OUTSIDE_TILES,
            "use_tms_filenames": cls.KEY_USE_TMS_CONVENTION,
            "use_mbtiles_compression": cls.KEY_USE_MBTILES_COMPRESSION,
            "write_json": cls.KEY_WRITE_JSON_METADATA,
            "write_overview": cls.KEY_WRITE_OVERVIEW,
            "write_mapurl": cls.KEY_WRITE_MAPURL,
            "write_viewer": cls.KEY_WRITE_LEAFLET_VIEWER,
        }

        for old_key, new_key in settings_key_map.items():
            value = old_settings.value(old_key)
            if value is not None:
                qgs_settings.setValue(new_key, value)
                old_settings.remove(old_key)

        # remove deprecated settings
        for deprecated_key in (
            "extentCanvas",
            "extentFull",
            "extentLayer",
            "keepRatio",
            "outputToDir",
            "outputToDir_Path",
            "outputToNGM",
            "outputToNGM_Path",
            "outputToZip",
            "outputToZip_Path",
            "tileHeight",
            "transparency",
        ):
            old_settings.remove(deprecated_key)
