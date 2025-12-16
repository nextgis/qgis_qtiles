import json

from qgis.core import QgsMapRendererCustomPainterJob
from qgis.PyQt.QtCore import QFile, QIODevice, Qt
from qgis.PyQt.QtGui import QImage, QPainter

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
        if self.__options.write_overview:
            self.__write_overview()

        if self.__options.write_mapurl:
            self.__write_mapurl()

        if self.__options.write_viewer:
            self.__write_viewer()

        if self.__options.write_json_metadata:
            self.__write_json_metadata()

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

        image.save(str(file_path), image_format, self.__options.quality)

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

        with open(str(file_path), "w", encoding="utf-8") as mapurl:
            mapurl.write(
                f"url={self.__root_dir}/ZZZ/XXX/YYY.{self.__options.image_format}\n"
            )
            mapurl.write(f"minzoom={self.__options.min_zoom}\n")
            mapurl.write(f"maxzoom={self.__options.max_zoom}\n")
            mapurl.write(f"center={center_x} {center_y}\n")
            mapurl.write(f"type={tile_server}\n")

    def __write_viewer(self) -> None:
        """
        Generates a Leaflet viewer directory for the tile set.

        :returns: None
        """
        template_file = QFile(":/plugins/qtiles/resources/viewer.html")
        if not template_file.open(QIODevice.OpenModeFlag.ReadOnly):
            return

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
        with open(str(index_path), "wb") as html_viewer:
            html_viewer.write(output_html.encode("utf-8"))

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
        with open(str(file_path), "w", encoding="utf-8") as json_file:
            json.dump(info, json_file)
