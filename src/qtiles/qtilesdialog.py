# ******************************************************************************
#
# QTiles
# ---------------------------------------------------------
# Generates tiles from QGIS project
#
# Copyright (C) 2012-2022 NextGIS (info@nextgis.com)
#
# This source is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option)
# any later version.
#
# This code is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# A copy of the GNU General Public License is available on the World Wide Web
# at <http://www.gnu.org/licenses/>. You can also obtain it by writing
# to the Free Software Foundation, 51 Franklin Street, Suite 500 Boston,
# MA 02110-1335 USA.
#
# ******************************************************************************
import operator
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from qgis.gui import QgsInterface

from qgis.core import QgsFileUtils, QgsMapLayer
from qgis.gui import QgsGui
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QFileInfo, Qt, pyqtSlot
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMessageBox,
)

from qtiles.restrictions import OpenStreetMapRestriction
from qtiles.tile import Tile

from . import qtiles_utils as utils
from . import tilingthread
from .compat import QgsSettings

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "ui/qtilesdialogbase.ui")
)


class QTilesDialog(QDialog, FORM_CLASS):
    """
    QTilesDialog is the main dialog for configuring
    and generating map tiles from a QGIS project.
    """

    # MAX_ZOOM_LEVEL = 18
    MIN_ZOOM_LEVEL = 0

    def __init__(self, iface: "QgsInterface") -> None:
        """
        Initializes the QTilesDialog with the given QGIS interface.

        :param iface: The QGIS interface object for interacting with the QGIS application.
        """
        super().__init__()
        self.setupUi(self)

        self.setObjectName("qtiles_main_window")
        QgsGui.enableAutoGeometryRestore(self, "qtiles_main_window")

        self.btnOk = self.buttonBox.addButton(
            self.tr("Run"), QDialogButtonBox.ButtonRole.AcceptRole
        )

        # self.spnZoomMax.setMaximum(self.MAX_ZOOM_LEVEL)
        self.spnZoomMax.setMinimum(self.MIN_ZOOM_LEVEL)
        # self.spnZoomMin.setMaximum(self.MAX_ZOOM_LEVEL)
        self.spnZoomMin.setMinimum(self.MIN_ZOOM_LEVEL)

        self.spnZoomMin.valueChanged.connect(self.spnZoomMax.setMinimum)
        self.spnZoomMax.valueChanged.connect(self.spnZoomMin.setMaximum)

        self.iface = iface

        self.verticalLayout_2.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.workThread = None

        self.FORMATS = {
            self.tr("ZIP archives (*.zip *.ZIP)"): ".zip",
            self.tr("MBTiles databases (*.mbtiles *.MBTILES)"): ".mbtiles",
            self.tr("PMTiles archives (*.pmtiles *.PMTILES)"): ".pmtiles",
        }

        self.settings = QgsSettings("NextGIS", "QTiles")
        self.grpParameters.setSettings(self.settings)
        self.btnClose = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Close
        )
        self.rbExtentLayer.toggled.connect(self.__toggleLayerSelector)
        self.chkLockRatio.stateChanged.connect(self.__toggleHeightEdit)
        self.spnTileWidth.valueChanged.connect(self.__updateTileSize)
        self.btnBrowse.clicked.connect(self.__select_output)
        self.cmbFormat.activated.connect(self.formatChanged)

        self.rbOutputZip.toggled.connect(self.__toggleTarget)
        self.rbOutputDir.toggled.connect(self.__toggleTarget)
        self.rbOutputNGM.toggled.connect(self.__toggleTarget)
        self.rbOutputNGM.setIcon(
            QIcon(":/plugins/qtiles/icons/ngm_index_24x24.png")
        )

        self.lInfoIconOutputZip.linkActivated.connect(self.show_output_info)
        self.lInfoIconOutputDir.linkActivated.connect(self.show_output_info)
        self.lInfoIconOutputNGM.linkActivated.connect(self.show_output_info)

        self.manageGui()

    def show_output_info(self, href: str) -> None:
        """
        Displays information about the selected output type.

        :param href: The hyperlink reference associated with the clicked icon.
        """
        title = self.tr("Output type info")
        message = ""
        if self.sender() is self.lInfoIconOutputZip:
            message = self.tr("Save tiles as Zip or MBTiles")
        elif self.sender() is self.lInfoIconOutputDir:
            message = self.tr("Save tiles as directory structure")
        elif self.sender() is self.lInfoIconOutputNGM:
            message = (
                "<table cellspacing='10'> <tr> \
                        <td> \
                            <img src=':/plugins/qtiles/icons/ngm_index_24x24.png'/> \
                        </td> \
                        <td> \
                            %s \
                        </td> \
                    </tr> </table>"
                % self.tr(
                    "Prepare package for <a href='http://nextgis.ru/en/nextgis-mobile/'> NextGIS Mobile </a>"
                )
            )

        # QMessageBox.information(
        #     self,
        #     title,
        #     message
        # )
        msgBox = QMessageBox()
        msgBox.setWindowTitle(title)
        msgBox.setText(message)
        msgBox.exec()

    def formatChanged(self) -> None:
        """
        Updates the GUI based on the selected output format.

        This method enables or disables certain input fields depending on
        whether the selected format is JPG or another format.
        """
        if self.cmbFormat.currentText() == "JPG":
            self.spnTransparency.setEnabled(False)
            self.spnQuality.setEnabled(True)
        else:
            self.spnTransparency.setEnabled(True)
            self.spnQuality.setEnabled(False)

    def manageGui(self) -> None:
        """
        Configures the GUI elements based on saved settings and user input.
        """
        layers = utils.getMapLayers()
        for layer in sorted(
            iter(list(layers.items())), key=operator.itemgetter(1)
        ):
            groupName = utils.getLayerGroup(layer[0])
            if groupName == "":
                self.cmbLayers.addItem(layer[1], layer[0])
            else:
                self.cmbLayers.addItem(
                    "%s - %s" % (layer[1], groupName), layer[0]
                )

        self.rbOutputZip.setChecked(
            self.settings.value("outputToZip", True, type=bool)
        )
        self.rbOutputDir.setChecked(
            self.settings.value("outputToDir", False, type=bool)
        )
        self.rbOutputNGM.setChecked(
            self.settings.value("outputToNGM", False, type=bool)
        )
        if self.rbOutputZip.isChecked():
            self.leDirectoryName.setEnabled(False)
            self.leTilesFroNGM.setEnabled(False)
        elif self.rbOutputDir.isChecked():
            self.leZipFileName.setEnabled(False)
            self.leTilesFroNGM.setEnabled(False)
        elif self.rbOutputNGM.isChecked():
            self.leZipFileName.setEnabled(False)
            self.leDirectoryName.setEnabled(False)
        else:
            self.leZipFileName.setEnabled(False)
            self.leDirectoryName.setEnabled(False)
            self.leTilesFroNGM.setEnabled(False)

        self.leZipFileName.setText(self.settings.value("outputToZip_Path", ""))
        self.leDirectoryName.setText(
            self.settings.value("outputToDir_Path", "")
        )
        self.leTilesFroNGM.setText(self.settings.value("outputToNGM_Path", ""))

        self.cmbLayers.setEnabled(False)
        self.leRootDir.setText(self.settings.value("rootDir", "Mapnik"))
        self.rbExtentCanvas.setChecked(
            self.settings.value("extentCanvas", True, type=bool)
        )
        self.rbExtentFull.setChecked(
            self.settings.value("extentFull", False, type=bool)
        )
        self.rbExtentLayer.setChecked(
            self.settings.value("extentLayer", False, type=bool)
        )
        self.spnZoomMin.setValue(self.settings.value("minZoom", 0, type=int))
        self.spnZoomMax.setValue(self.settings.value("maxZoom", 18, type=int))
        self.chkLockRatio.setChecked(
            self.settings.value("keepRatio", True, type=bool)
        )
        self.spnTileWidth.setValue(
            self.settings.value("tileWidth", 256, type=int)
        )
        self.spnTileHeight.setValue(
            self.settings.value("tileHeight", 256, type=int)
        )
        self.spnTransparency.setValue(
            self.settings.value("transparency", 255, type=int)
        )
        self.spnQuality.setValue(self.settings.value("quality", 70, type=int))
        self.cmbFormat.setCurrentIndex(int(self.settings.value("format", 0)))
        self.chkAntialiasing.setChecked(
            self.settings.value("enable_antialiasing", False, type=bool)
        )
        self.chkTMSConvention.setChecked(
            self.settings.value("use_tms_filenames", False, type=bool)
        )
        self.chkMBTilesCompression.setChecked(
            self.settings.value("use_mbtiles_compression", False, type=bool)
        )
        self.chkWriteJson.setChecked(
            self.settings.value("write_json", False, type=bool)
        )
        self.chkWriteOverview.setChecked(
            self.settings.value("write_overview", False, type=bool)
        )
        self.chkWriteMapurl.setChecked(
            self.settings.value("write_mapurl", False, type=bool)
        )
        self.chkWriteViewer.setChecked(
            self.settings.value("write_viewer", False, type=bool)
        )
        self.chkRenderOutsideTiles.setChecked(
            self.settings.value("renderOutsideTiles", True, type=bool)
        )

        self.formatChanged()

    def reject(self) -> None:
        """
        Closes the dialog without saving changes.
        """
        super().reject()

    def accept(self) -> None:
        """
        Validates user input and starts the tile generation process.
        """
        if self.rbOutputZip.isChecked():
            output_path_str = self.leZipFileName.text()
        elif self.rbOutputDir.isChecked():
            output_path_str = self.leDirectoryName.text()
        elif self.rbOutputNGM.isChecked():
            output_path_str = self.leTilesFroNGM.text()
        else:
            output_path_str = ""

        if not output_path_str:
            QMessageBox.warning(
                self,
                self.tr("Output not set"),
                self.tr("Output path is not set. Please specify a path."),
            )
            return

        output_path = Path(output_path_str)

        tileset_name = self.leRootDir.text()
        if not self.__is_tileset_name_valid(tileset_name):
            return

        if not self.__is_input_parameters_valid():
            return

        canvas = self.iface.mapCanvas()
        if self.rbExtentCanvas.isChecked():
            extent = canvas.extent()
        elif self.rbExtentFull.isChecked():
            extent = canvas.fullExtent()
        else:
            layer = utils.getLayerById(
                self.cmbLayers.itemData(self.cmbLayers.currentIndex())
            )
            extent = canvas.mapSettings().layerExtentToOutputExtent(
                layer, layer.extent()
            )

        target_extent = utils.compute_target_extent(canvas, extent)

        layers = canvas.layers()

        tms_convention = (
            self.chkTMSConvention.isChecked()
            and self.chkTMSConvention.isEnabled()
        )
        if output_path.suffix.lower() == ".mbtiles":
            tms_convention = True

        use_tms = -1 if tms_convention else 1

        initial_tile = Tile(0, 0, 0, use_tms)
        min_zoom = self.spnZoomMin.value()
        max_zoom = self.spnZoomMax.value()
        render_outside_tiles = self.chkRenderOutsideTiles.isChecked()

        tiles = utils.count_tiles(
            initial_tile,
            layers,
            target_extent,
            min_zoom,
            max_zoom,
            render_outside_tiles,
        )

        if tiles is None:
            QMessageBox.warning(
                self,
                self.tr("Error"),
                self.tr(
                    "The current map extent does not intersect with the tiles. "
                    "Please check the extent and zoom level. "
                    "This could be caused by an invalid or out-of-bounds extent."
                ),
                QMessageBox.StandardButton.Ok,
            )
            return

        tiles_count = len(tiles)

        if tiles_count > utils.TILES_COUNT_TRESHOLD:
            if not self.__confirm_continue_threshold(
                utils.TILES_COUNT_TRESHOLD
            ):
                return

        layers = self.__validate_osm_restriction(layers, tiles_count)
        if layers is None:
            return

        if self.rbOutputZip.isChecked() or self.rbOutputNGM.isChecked():
            if not self.__confirm_and_overwrite_output_path(
                output_path, self.tr("tileset output file"), is_directory=False
            ):
                return

        write_mapurl = (
            self.chkWriteMapurl.isEnabled() and self.chkWriteMapurl.isChecked()
        )
        write_viewer = (
            self.chkWriteViewer.isEnabled() and self.chkWriteViewer.isChecked()
        )

        if write_viewer:
            viewer_dir = output_path / f"{tileset_name}_viewer"
            if not self.__confirm_and_overwrite_output_path(
                viewer_dir, self.tr("viewer directory"), is_directory=True
            ):
                return

        if self.rbOutputDir.isChecked():
            tileset_dir = output_path / tileset_name
            if not self.__confirm_and_overwrite_output_path(
                tileset_dir,
                self.tr("tileset output directory"),
                is_directory=True,
            ):
                return

        self.__save_settings()

        self.workThread = tilingthread.TilingThread(
            tiles,
            layers,
            target_extent,
            min_zoom,
            max_zoom,
            self.spnTileWidth.value(),
            self.spnTileHeight.value(),
            self.spnTransparency.value(),
            self.spnQuality.value(),
            self.spin_box_dpi.value(),
            self.cmbFormat.currentText(),
            output_path,
            self.leRootDir.text(),
            self.chkAntialiasing.isChecked(),
            tms_convention,
            self.chkMBTilesCompression.isChecked(),
            self.chkWriteJson.isChecked(),
            self.chkWriteOverview.isChecked(),
            write_mapurl,
            write_viewer,
        )

        self.workThread.rangeChanged.connect(self.setProgressRange)
        self.workThread.updateProgress.connect(self.updateProgress)
        self.workThread.processFinished.connect(self.processFinished)
        self.workThread.processInterrupted.connect(self.processInterrupted)
        self.btnOk.setEnabled(False)
        self.btnClose.setText(self.tr("Cancel"))
        self.buttonBox.rejected.disconnect(self.reject)
        self.btnClose.clicked.connect(self.stopProcessing)
        self.workThread.start()

    def __confirm_continue_threshold(self, tiles_count_threshold: int) -> bool:
        """
        Confirms whether to proceed with tile generation
        when the estimated tile count exceeds a given threshold.

        :param tiles_count_threshold: The estimated threshold of tile count
                                      that triggers the confirmation.
        """
        reply = QMessageBox.question(
            self,
            self.tr("Confirmation"),
            self.tr("Estimate number of tiles more then {}! Continue?").format(
                tiles_count_threshold
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        return reply == QMessageBox.StandardButton.Yes

    @pyqtSlot(str, int)
    def setProgressRange(self, message: str, value: int) -> None:
        """
        Sets the progress bar range and updates its message.

        :param message: A string containing the message to be displayed
                        on the progress bar.
        :param value: The total value indicating the range of progress.
        """
        self.progressBar.setFormat(message)
        self.progressBar.setRange(0, value)

    @pyqtSlot()
    def updateProgress(self) -> None:
        """
        Updates the progress bar by incrementing its current value.
        """
        self.progressBar.setValue(self.progressBar.value() + 1)

    @pyqtSlot()
    def processInterrupted(self) -> None:
        """
        Restores the GUI state after the tile generation process is interrupted.
        """
        self.restoreGui()

    @pyqtSlot()
    def processFinished(self) -> None:
        """
        Restores the GUI state and stops
        the tile generation process when it is completed.
        """
        self.stopProcessing()
        self.restoreGui()

    def stopProcessing(self) -> None:
        """
        Stops the tile generation process if it is running.
        """
        if self.workThread is not None:
            self.workThread.stop()
            self.workThread = None

    def restoreGui(self) -> None:
        """
        Restores the initial GUI state
        after a process has finished or been interrupted.
        """
        self.progressBar.setFormat("%p%")
        self.progressBar.setRange(0, 1)
        self.progressBar.setValue(0)
        self.buttonBox.rejected.connect(self.reject)
        self.btnClose.clicked.disconnect(self.stopProcessing)
        self.btnClose.setText(self.tr("Close"))
        self.btnOk.setEnabled(True)

    def __toggleTarget(self, checked: bool) -> None:
        """
        Toggles the availability of target-related input fields.

        This method is triggered when the user selects a different output
        target (e.g., ZIP, directory, or NGM package).

        :param checked: A boolean indicating whether the target is selected.
        """
        if checked:
            if self.sender() is self.rbOutputZip:
                self.leZipFileName.setEnabled(True)
                self.leDirectoryName.setEnabled(False)
                self.leTilesFroNGM.setEnabled(False)
                self.chkWriteMapurl.setEnabled(False)
                self.chkWriteViewer.setEnabled(False)
                self.chkWriteJson.setEnabled(True)

                self.spnTileWidth.setEnabled(True)
                self.chkLockRatio.setEnabled(True)
                self.cmbFormat.setEnabled(True)
                self.chkMBTilesCompression.setEnabled(True)

                self.chkWriteOverview.setEnabled(True)
            elif self.sender() is self.rbOutputDir:
                self.leZipFileName.setEnabled(False)
                self.leDirectoryName.setEnabled(True)
                self.leTilesFroNGM.setEnabled(False)
                self.chkWriteMapurl.setEnabled(True)
                self.chkWriteViewer.setEnabled(True)
                self.chkWriteJson.setEnabled(True)
                self.chkMBTilesCompression.setEnabled(False)

                self.spnTileWidth.setEnabled(True)
                self.chkLockRatio.setEnabled(True)
                self.cmbFormat.setEnabled(True)

                self.chkWriteOverview.setEnabled(True)
            elif self.sender() is self.rbOutputNGM:
                self.leZipFileName.setEnabled(False)
                self.leDirectoryName.setEnabled(False)
                self.leTilesFroNGM.setEnabled(True)
                self.chkWriteMapurl.setEnabled(False)
                self.chkWriteViewer.setEnabled(False)
                self.chkMBTilesCompression.setEnabled(False)

                self.spnTileWidth.setValue(256)
                self.spnTileWidth.setEnabled(False)
                self.chkLockRatio.setCheckState(Qt.CheckState.Checked)
                self.chkLockRatio.setEnabled(False)
                self.cmbFormat.setCurrentIndex(0)
                self.cmbFormat.setEnabled(True)

                self.chkWriteOverview.setChecked(False)
                self.chkWriteOverview.setEnabled(False)

                self.chkWriteJson.setChecked(False)
                self.chkWriteJson.setEnabled(False)

    def __toggleLayerSelector(self, checked: bool) -> None:
        """
        Toggles the visibility of the layer selector based on user input.

        :param checked: A boolean indicating whether the layer selector should be visible.
        """
        self.cmbLayers.setEnabled(checked)

    def __toggleHeightEdit(self, state: int) -> None:
        """
        Enables or disables the height input field based on the lock ratio
        checkbox.

        :param state: The state of the lock ratio checkbox (checked or unchecked).
        """
        if state == Qt.CheckState.Checked:
            self.lblHeight.setEnabled(False)
            self.spnTileHeight.setEnabled(False)
            self.spnTileHeight.setValue(self.spnTileWidth.value())
        else:
            self.lblHeight.setEnabled(True)
            self.spnTileHeight.setEnabled(True)

    @pyqtSlot(int)
    def __updateTileSize(self, value: int) -> None:
        """
        Updates the tile size based on user input.

        This method ensures that the tile width and height remain consistent
        when the user changes one of the dimensions.

        :param value: The new value for the tile size.
        """
        if self.chkLockRatio.isChecked():
            self.spnTileHeight.setValue(value)

    def __select_output(self) -> None:
        """
        Opens a file dialog for selecting the output path.
        """
        if self.rbOutputZip.isChecked():
            file_directory = QFileInfo(
                self.settings.value("outputToZip_Path", ".")
            ).absolutePath()
            output_path, output_filter = QFileDialog.getSaveFileName(
                self,
                self.tr("Save to file"),
                file_directory,
                ";;".join(iter(list(self.FORMATS.keys()))),
            )
            if not output_path:
                return

            ext = self.FORMATS.get(output_filter)
            if not ext:
                return

            output_path = QgsFileUtils.ensureFileNameHasExtension(
                output_path, [ext]
            )

            self.leZipFileName.setText(output_path)
            self.settings.setValue(
                "outputToZip_Path", QFileInfo(output_path).absoluteFilePath()
            )

            if ext == ".pmtiles":
                self.spnTileWidth.setValue(512)
                self.spnTileHeight.setValue(512)

                self.chkTMSConvention.setEnabled(False)
            else:
                self.chkTMSConvention.setEnabled(True)

        elif self.rbOutputDir.isChecked():
            dir_directory = QFileInfo(
                self.settings.value("outputToDir_Path", ".")
            ).absolutePath()
            output_path = QFileDialog.getExistingDirectory(
                self,
                self.tr("Save to directory"),
                dir_directory,
                QFileDialog.Option.ShowDirsOnly,
            )
            if not output_path:
                return
            self.leDirectoryName.setText(output_path)
            self.settings.setValue(
                "outputToDir_Path", QFileInfo(output_path).absoluteFilePath()
            )

        elif self.rbOutputNGM.isChecked():
            zip_directory = QFileInfo(
                self.settings.value("outputToNGM_Path", ".")
            ).absolutePath()
            output_path, output_filter = QFileDialog.getSaveFileName(
                self, self.tr("Save to file"), zip_directory, "NGRC (*.ngrc)"
            )
            if not output_path:
                return

            output_path = QgsFileUtils.ensureFileNameHasExtension(
                output_path, [".ngrc"]
            )

            self.leTilesFroNGM.setText(output_path)
            self.settings.setValue(
                "outputToNGM_Path", QFileInfo(output_path).absoluteFilePath()
            )

    def __is_input_parameters_valid(self) -> bool:
        if (
            self.rbExtentLayer.isChecked()
            and self.cmbLayers.currentIndex() < 0
        ):
            QMessageBox.warning(
                self,
                self.tr("Layer not selected"),
                self.tr("Please select a layer and try again."),
            )
            return False

        min_zoom = self.spnZoomMin.value()
        max_zoom = self.spnZoomMax.value()
        if min_zoom > max_zoom:
            QMessageBox.warning(
                self,
                self.tr("Wrong zoom"),
                self.tr(
                    "Maximum zoom value is lower than minimum. Please correct this and try again."
                ),
            )
            return False

        return True

    def __save_settings(self) -> None:
        self.settings.setValue("rootDir", self.leRootDir.text())
        self.settings.setValue("outputToZip", self.rbOutputZip.isChecked())
        self.settings.setValue("outputToDir", self.rbOutputDir.isChecked())
        self.settings.setValue("outputToNGM", self.rbOutputNGM.isChecked())
        self.settings.setValue("extentCanvas", self.rbExtentCanvas.isChecked())
        self.settings.setValue("extentFull", self.rbExtentFull.isChecked())
        self.settings.setValue("extentLayer", self.rbExtentLayer.isChecked())
        self.settings.setValue("minZoom", self.spnZoomMin.value())
        self.settings.setValue("maxZoom", self.spnZoomMax.value())
        self.settings.setValue("keepRatio", self.chkLockRatio.isChecked())
        self.settings.setValue("tileWidth", self.spnTileWidth.value())
        self.settings.setValue("tileHeight", self.spnTileHeight.value())
        self.settings.setValue("format", self.cmbFormat.currentIndex())
        self.settings.setValue("transparency", self.spnTransparency.value())
        self.settings.setValue("quality", self.spnQuality.value())
        self.settings.setValue(
            "enable_antialiasing", self.chkAntialiasing.isChecked()
        )
        self.settings.setValue(
            "use_tms_filenames", self.chkTMSConvention.isChecked()
        )
        self.settings.setValue(
            "use_mbtiles_compression", self.chkMBTilesCompression.isChecked()
        )
        self.settings.setValue("write_json", self.chkWriteJson.isChecked())
        self.settings.setValue(
            "write_overview", self.chkWriteOverview.isChecked()
        )
        self.settings.setValue("write_mapurl", self.chkWriteMapurl.isChecked())
        self.settings.setValue("write_viewer", self.chkWriteViewer.isChecked())
        self.settings.setValue(
            "renderOutsideTiles", self.chkRenderOutsideTiles.isChecked()
        )

    def __validate_osm_restriction(
        self, layers: List[QgsMapLayer], tiles_count: int
    ) -> Optional[List[QgsMapLayer]]:
        """
        Validates OSM tile usage restrictions and optionally filters out
        prohibited layers after user confirmation.

        :param layers: List of canvas layers.
        :param tiles_count: Final number of tiles to be generated.
        :returns:
            - Updated list of layers if generation can continue.
            - None if the user cancels or all OSM layers must be skipped.
        """
        osm_restriction = OpenStreetMapRestriction()
        is_violated, message, skipped_layers = (
            osm_restriction.validate_restriction(layers, tiles_count)
        )

        if not is_violated:
            return layers

        if len(skipped_layers) == len(layers):
            QMessageBox.warning(
                self,
                self.tr("OpenStreetMap Layer Restriction"),
                message,
                QMessageBox.StandardButton.Ok,
            )
            return None

        reply = QMessageBox.question(
            self,
            self.tr("OpenStreetMap Layer Restriction"),
            message
            + "<br><br>"
            + self.tr(
                "Are you sure you want to continue without OpenStreetMap layers?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return None

        return [layer for layer in layers if layer not in skipped_layers]

    def __confirm_and_overwrite_output_path(
        self, output_path: Path, description: str, is_directory: bool = False
    ) -> bool:
        """
        Checks if a file or directory exists, prompts the user for confirmation
        to overwrite, and attempts to remove it.

        :param output_path: The path to the file or directory.
        :param description: Human-readable description of the object
            (e.g., 'tileset directory', 'viewer directory', 'output file').
        :param is_directory: True if the path is a directory, False if a file.

        :return: True if path was successfully removed or did not exist;
            False if user cancelled or an error occurred.
        """
        if not output_path.exists():
            return True

        message = self.tr(
            "The {desc} already exists and will be overwritten:\n"
            "{path}\n\n"
            "Are you sure you want to continue?"
        ).format(desc=description, path=str(output_path))

        reply = QMessageBox.question(
            self,
            self.tr("Output path exists"),
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return False

        try:
            if is_directory:
                shutil.rmtree(output_path)
            else:
                output_path.unlink()
            return True
        except Exception as error:
            QMessageBox.critical(
                self,
                self.tr("Cannot overwrite"),
                self.tr(
                    "Failed to overwrite {desc}:\n{path}\n\nError: {err}"
                ).format(
                    desc=description, path=str(output_path), err=str(error)
                ),
            )
            return False

    def __is_tileset_name_valid(self, tileset_name: str) -> bool:
        """
        Validates the tileset name to ensure it is safe for use as a folder name.

        :param tileset_name: The name of the tileset folder provided by the user.
        :return: True if the tileset name is valid, False otherwise.
        """
        forbidden_names = {".", ".."}
        forbidden_chars = {"/", "\\", ":", "*", "?", '"', "<", ">", "|"}

        if not tileset_name.strip():
            QMessageBox.warning(
                self,
                self.tr("Invalid tileset name"),
                self.tr(
                    "Tileset name cannot be empty. Please specify a name."
                ),
            )
            return False

        if tileset_name in forbidden_names or any(
            char in tileset_name for char in forbidden_chars
        ):
            QMessageBox.warning(
                self,
                self.tr("Invalid tileset name"),
                self.tr(
                    "Tileset name contains forbidden characters or reserved names. "
                    "Please choose a different name."
                ),
            )
            return False

        return True
