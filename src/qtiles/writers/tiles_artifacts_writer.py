import json
from typing import Callable, List

from qgis.core import QgsApplication, QgsMapRendererCustomPainterJob
from qgis.PyQt.QtCore import QFile, QIODevice, Qt
from qgis.PyQt.QtGui import QImage, QPainter

from qtiles.core.exceptions import TileGenerationError, TileGenerationWarning
from qtiles.core.logging import logger
from qtiles.writers import utils
from qtiles.writers.save_tiles_options import SaveTilesOptions


class TilesetArtifactsWriter:
    """
    Writes auxiliary artifacts for a generated tile set.
    """

    def __init__(self, options: SaveTilesOptions):
        """
        Initializes the artifacts writer.

        :param options: Configuration options controlling which
                        auxiliary artifacts should be generated.
        :type options: SaveTilesOptions
        """
        self.__options = options
        self.__output_path = options.output_path
        self.__root_dir = options.root_dir

    def write(self) -> None:
        """
        Writes all auxiliary artifacts according to options.

        :returns: None
        """
        has_warnings = False

        if self.__options.write_json_metadata:
            has_warnings |= not self.__try_write_artifact(
                self.__write_json_metadata
            )
        if self.__options.write_overview:
            has_warnings |= not self.__try_write_artifact(
                self.__write_overview
            )
        if self.__options.write_mapurl:
            has_warnings |= not self.__try_write_artifact(self.__write_mapurl)
        if self.__options.write_viewer:
            has_warnings |= not self.__try_write_artifact(self.__write_viewer)

        if has_warnings:
            # fmt: off
            raise TileGenerationWarning(
                log_message="Some auxiliary artifacts were not fully generated.",
                user_message=QgsApplication.translate(
                    "QTiles",
                    "Some auxiliary artifacts were not fully generated."
                ),
                detail=QgsApplication.translate(
                    "QTiles",
                    "One or more auxiliary artifacts could not be generated. Please check the log for details."
                ),
            )
            # fmt: on

    def __try_write_artifact(self, write_function: Callable[[], None]) -> bool:
        """
        Helper method to attempt writing an artifact and handle warnings.

        :param write_function: The function that performs the writing of the artifact.
        :returns: True if the artifact was written successfully, False if a warning occurred.
        """
        try:
            write_function()
            return True
        except TileGenerationWarning as warning:
            logger.warning(str(warning))
            return False

    def __write_overview(self) -> None:
        """
        Generates an overview image of the entire tile set.

        :returns: None
        """
        image_format = self.__options.image_format
        map_settings = self.__options.overview_map_settings

        image = QImage(map_settings.outputSize(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)

        dpm = round(map_settings.outputDpi() / 25.4 * 1000)
        image.setDotsPerMeterX(dpm)
        image.setDotsPerMeterY(dpm)

        painter = QPainter(image)
        job = QgsMapRendererCustomPainterJob(map_settings, painter)
        job.renderSynchronously()
        painter.end()

        if self.__output_path.is_dir():
            file_path = (
                self.__output_path
                / f"{self.__root_dir}.{image_format.lower()}"
            )
        else:
            base_name = self.__output_path.stem
            file_path = (
                self.__output_path.parent
                / f"{base_name}.{image_format.lower()}"
            )

        # fmt: off
        utils.ensure_operation_succeeded(
            image.save(str(file_path), image_format, self.__options.quality),
            log_message=f"Failed to save overview image: {file_path}",
            user_message=QgsApplication.translate(
                "QTiles", "Overview image was not generated."
            ),
            detail=QgsApplication.translate(
                "QTiles",
                "Could not save the overview image to '{path}'."
            ).format(path=file_path),
            warning=True,
        )
        # fmt: on

    def __write_mapurl(self) -> None:
        """
        Writes a .mapurl file describing the tile set.

        :returns: None
        """
        file_path = self.__output_path / f"{self.__root_dir}.mapurl"

        extent = self.__options.extent
        center_x = extent.center().x()
        center_y = extent.center().y()

        tile_server = "tms" if self.__options.tms_convention else "google"

        try:
            with open(str(file_path), "w", encoding="utf-8") as mapurl:
                mapurl.write(
                    f"url={self.__root_dir}/ZZZ/XXX/YYY.{self.__options.image_format}\n"
                )
                mapurl.write(f"minzoom={self.__options.min_zoom}\n")
                mapurl.write(f"maxzoom={self.__options.max_zoom}\n")
                mapurl.write(f"center={center_x} {center_y}\n")
                mapurl.write(f"type={tile_server}\n")
        except IOError as error:
            # fmt: off
            raise TileGenerationError(
                log_message=f"Failed to write .mapurl file: {file_path}",
                user_message=QgsApplication.translate(
                    "QTiles", ".mapurl file was not generated."
                ),
                detail=QgsApplication.translate(
                    "QTiles",
                    "Could not write the .mapurl file to '{path}'."
                ).format(path=file_path, error=str(error)),
            ) from error
            # fmt: on

    def __write_viewer(self) -> None:
        """
        Generates a Leaflet viewer directory for the tile set.

        :returns: None
        """
        template_file = QFile(":/plugins/qtiles/resources/viewer.html")
        # fmt: off
        utils.ensure_operation_succeeded(
            template_file.open(QIODevice.OpenModeFlag.ReadOnly),
            log_message="Failed to open viewer template resource",
            user_message=QgsApplication.translate(
                "QTiles", "Viewer files were not fully generated."
            ),
            detail=QgsApplication.translate(
                "QTiles",
                "Could not read the embedded HTML template for the viewer."
            ),
            warning=True,
        )
        # fmt: on

        html = template_file.readAll().data().decode()
        template_file.close()
        viewer_template = utils.MyTemplate(html)

        viewer_dir = self.__output_path / f"{self.__root_dir}_viewer"
        utils.create_viewer_directory(viewer_dir)

        tiles_dir_relative = f"../{self.__root_dir}"
        extent = self.__options.extent
        substitutions = {
            "tilesdir": tiles_dir_relative,
            "tilesext": self.__options.image_format.lower(),
            "tilesetname": self.__root_dir,
            "tms": "true" if self.__options.tms_convention else "false",
            "centerx": extent.center().x(),
            "centery": extent.center().y(),
            "avgzoom": (self.__options.max_zoom + self.__options.min_zoom) / 2,
            "maxzoom": self.__options.max_zoom,
        }

        output_html = viewer_template.substitute(substitutions)
        index_path = viewer_dir / "index.html"
        try:
            with open(str(index_path), "wb") as html_viewer:
                html_viewer.write(output_html.encode("utf-8"))
        except IOError as error:
            # fmt: off
            raise TileGenerationWarning(
                log_message=f"Failed to write viewer HTML file: {index_path}",
                user_message=QgsApplication.translate(
                    "QTiles", "Viewer files were not fully generated."
                ),
                detail=QgsApplication.translate(
                    "QTiles",
                    "Could not write the viewer HTML file to '{path}'."
                ).format(path=index_path, error=str(error)),
            ) from error
            # fmt: on

    def __write_json_metadata(self) -> None:
        """
        Writes a JSON metadata file describing the tile set.

        :returns: None
        """
        if self.__output_path.is_dir():
            file_path = self.__output_path / f"{self.__root_dir}.json"
        else:
            base_name = self.__output_path.stem
            file_path = self.__output_path.parent / f"{base_name}.json"

        extent = self.__options.extent
        info = {
            "name": self.__root_dir,
            "format": self.__options.image_format.lower(),
            "minZoom": self.__options.min_zoom,
            "maxZoom": self.__options.max_zoom,
            "bounds": [
                extent.xMinimum(),
                extent.yMinimum(),
                extent.xMaximum(),
                extent.yMaximum(),
            ],
        }
        try:
            with open(str(file_path), "w", encoding="utf-8") as json_file:
                json.dump(info, json_file)
        except IOError as error:
            # fmt: off
            raise TileGenerationError(
                log_message=f"Failed to write JSON metadata file: {file_path}",
                user_message=QgsApplication.translate(
                    "QTiles", "JSON metadata file was not generated."
                ),
                detail=QgsApplication.translate(
                    "QTiles",
                    "Could not write the JSON metadata file to '{path}'."
                ).format(path=file_path, error=str(error)),
            ) from error
            # fmt: on
