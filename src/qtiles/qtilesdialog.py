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
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from qgis.gui import QgsInterface

from qgis.core import QgsApplication, QgsMapLayer
from qgis.gui import QgsFileWidget, QgsGui
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QSize, Qt, pyqtSlot
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QSizePolicy,
    QToolButton,
)

from qtiles.aboutdialog import AboutDialog
from qtiles.restrictions import OpenStreetMapRestriction
from qtiles.tile import Tile
from qtiles.writers.enums import TilesWriterMode

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

        self.iface = iface

        self.setObjectName("qtiles_main_window")
        QgsGui.enableAutoGeometryRestore(self, "qtiles_main_window")

        self.setWindowIcon(QIcon(":/plugins/qtiles/icons/qtiles.svg"))

        self.output_format_combo_box.currentIndexChanged.connect(
            self.__on_output_format_changed
        )

        self.extent_widget.toggleDialogVisibility.connect(
            self.__on_extent_toggle_dialog_visibility
        )

        self.btnOk = self.buttonBox.addButton(
            self.tr("Run"), QDialogButtonBox.ButtonRole.AcceptRole
        )

        # self.spnZoomMax.setMaximum(self.MAX_ZOOM_LEVEL)
        self.spnZoomMax.setMinimum(self.MIN_ZOOM_LEVEL)
        # self.spnZoomMin.setMaximum(self.MAX_ZOOM_LEVEL)
        self.spnZoomMin.setMinimum(self.MIN_ZOOM_LEVEL)

        self.spnZoomMin.valueChanged.connect(self.spnZoomMax.setMinimum)
        self.spnZoomMax.valueChanged.connect(self.spnZoomMin.setMaximum)

        self.verticalLayout_2.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.workThread = None

        self.settings = QgsSettings("NextGIS", "QTiles")
        self.grpParameters.setSettings(self.settings)
        self.btnClose = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Close
        )

        self.cmbFormat.activated.connect(self.formatChanged)

        self.about_button.clicked.connect(self.__show_about)

        self.manageGui()

    def formatChanged(self) -> None:
        """
        Updates the GUI based on the selected output format.

        This method enables or disables certain input fields depending on
        whether the selected format is JPG or another format.
        """
        if self.cmbFormat.currentText() == "JPG":
            self.spnQuality.setEnabled(True)
            self.transparent_background_checkbox.setEnabled(False)
            self.transparent_background_checkbox.setChecked(False)
        else:
            self.spnQuality.setEnabled(False)
            self.transparent_background_checkbox.setEnabled(True)
            self.transparent_background_checkbox.setChecked(True)

    def manageGui(self) -> None:
        """
        Configures the GUI elements based on saved settings and user input.
        """
        file_widget_buttons = self.output_path_file_widget.findChildren(
            QToolButton
        )
        if file_widget_buttons:
            file_widget_buttons[1].setIcon(
                QgsApplication.getThemeIcon("mActionFileOpen.svg")
            )

        file_widget_line_edit = self.output_path_file_widget.lineEdit()

        preffered_policy = QSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        file_widget_line_edit.setSizePolicy(preffered_policy)

        self.output_path_file_widget.setConfirmOverwrite(False)
        file_widget_line_edit.setReadOnly(True)
        file_widget_line_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        file_widget_line_edit.setPlaceholderText(
            self.tr("Select output path…")
        )

        self.output_path_file_widget.setDefaultRoot(
            self.settings.value("last_output_dir", str(Path.home()))
        )

        self.__populate_output_format_combo_box()

        self.leRootDir.setText(self.settings.value("rootDir", "Mapnik"))
        self.spnZoomMin.setValue(self.settings.value("minZoom", 0, type=int))
        self.spnZoomMax.setValue(self.settings.value("maxZoom", 18, type=int))
        self.tile_size_spinbox.setValue(
            self.settings.value("tileWidth", 256, type=int)
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

        self.progressBar.setVisible(False)

        self.about_button.setIcon(
            QgsApplication.getThemeIcon("mActionPropertiesWidget.svg")
        )

        self.chkAntialiasing.setToolTip(
            self.tr(
                "Renders lines with antialiasing to reduce jagged edges. "
                "May reduce drawing performance."
            )
        )

        self.transparent_background_checkbox.setToolTip(
            self.tr(
                "Renders tiles with a transparent background using the current "
                "map canvas background color."
            )
        )

        self.chkRenderOutsideTiles.setToolTip(
            self.tr(
                "Generates all tiles within the target extent, even if they do not "
                "intersect any layer. May significantly increase the number of tiles."
            )
        )

        self.chkTMSConvention.setToolTip(
            self.tr(
                "Switches tile Y-axis orientation between TMS and Slippy Map conventions. "
                "If disabled, the Slippy Map convention is used by default."
            )
        )

        self.chkMBTilesCompression.setToolTip(
            self.tr(
                "Reduces MBTiles file size at the cost of processing time."
            )
        )

        self.chkWriteJson.setToolTip(
            self.tr("Writes a JSON file with basic tile set metadata.")
        )

        self.chkWriteOverview.setToolTip(
            self.tr(
                "Generates a single overview image of the entire tile set."
            )
        )

        self.chkWriteMapurl.setToolTip(
            self.tr("Writes a MapURL file describing the tile set.")
        )

        self.chkWriteViewer.setToolTip(
            self.tr(
                "Generates a simple Leaflet-based HTML viewer for the exported "
                "tile set."
            )
        )

        self.formatChanged()

    @pyqtSlot()
    def __show_about(self) -> None:
        """
        Displays the About dialog for the QTiles plugin.
        """
        package_name = str(Path(__file__).parent.name)
        about_dialog = AboutDialog(package_name)
        about_dialog.exec()

    def reject(self) -> None:
        """
        Closes the dialog without saving changes.
        """
        super().reject()

    def accept(self) -> None:
        """
        Validates user input and starts the tile generation process.
        """
        output_path_str = self.output_path_file_widget.filePath()

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
        extent = self.extent_widget.outputExtent()
        target_extent = utils.compute_target_extent(extent)

        layers = canvas.layers()

        tms_convention = self.chkTMSConvention.isChecked()
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

        writer_mode: TilesWriterMode = (
            self.output_format_combo_box.currentData()
        )

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

        if writer_mode.is_directory:
            tileset_path = output_path / tileset_name
            if not self.__confirm_and_overwrite_output_path(
                tileset_path,
                self.tr("tileset output directory"),
                is_directory=True,
            ):
                return
        else:
            if not self.__confirm_and_overwrite_output_path(
                output_path,
                self.tr("tileset output file"),
                is_directory=False,
            ):
                return

        self.__save_settings()

        self.workThread = tilingthread.TilingThread(
            tiles,
            layers,
            writer_mode,
            target_extent,
            min_zoom,
            max_zoom,
            self.tile_size_spinbox.value(),
            self.spnQuality.value(),
            self.spin_box_dpi.value(),
            self.cmbFormat.currentText(),
            output_path,
            self.leRootDir.text(),
            self.chkAntialiasing.isChecked(),
            self.transparent_background_checkbox.isChecked(),
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
        self.progressBar.setVisible(True)
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
        self.progressBar.setVisible(False)

        self.buttonBox.rejected.connect(self.reject)
        self.btnClose.clicked.disconnect(self.stopProcessing)
        self.btnClose.setText(self.tr("Close"))
        self.btnOk.setEnabled(True)

    def __on_output_format_changed(self, index: int) -> None:
        """
        Update UI state according to selected tiles writer mode.
        """
        writer_mode: Optional[TilesWriterMode] = (
            self.output_format_combo_box.itemData(index)
        )

        if writer_mode is None:
            return

        self.__configure_output_path_file_widget(writer_mode)

        self.chkWriteOverview.setEnabled(True)
        self.chkWriteJson.setEnabled(True)
        self.chkWriteMapurl.setEnabled(False)
        self.chkWriteViewer.setEnabled(False)

        self.chkMBTilesCompression.setEnabled(False)

        self.tile_size_spinbox.setEnabled(True)

        self.chkTMSConvention.setEnabled(True)

        if writer_mode.is_directory:
            self.chkWriteMapurl.setEnabled(True)
            self.chkWriteViewer.setEnabled(True)
            return

        self.chkWriteMapurl.setChecked(False)
        self.chkWriteViewer.setChecked(False)

        if writer_mode is TilesWriterMode.MBTILES:
            self.chkMBTilesCompression.setEnabled(True)

            self.chkTMSConvention.setChecked(True)
            self.chkTMSConvention.setEnabled(False)
            return

        if writer_mode is TilesWriterMode.PMTILES:
            self.tile_size_spinbox.setValue(512)

            self.chkTMSConvention.setChecked(False)
            self.chkTMSConvention.setEnabled(False)
            return

        if writer_mode is TilesWriterMode.NGM:
            self.tile_size_spinbox.setValue(256)
            self.tile_size_spinbox.setEnabled(False)

            self.chkWriteOverview.setChecked(False)
            self.chkWriteOverview.setEnabled(False)

            self.chkWriteJson.setChecked(False)
            self.chkWriteJson.setEnabled(False)

    def __is_input_parameters_valid(self) -> bool:
        if not self.extent_widget.isValid():
            QMessageBox.warning(
                self,
                self.tr("Extent not set"),
                self.tr("Please specify a valid map extent."),
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
        self.settings.setValue("minZoom", self.spnZoomMin.value())
        self.settings.setValue("maxZoom", self.spnZoomMax.value())
        self.settings.setValue("tileWidth", self.tile_size_spinbox.value())
        self.settings.setValue("format", self.cmbFormat.currentIndex())
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

    @pyqtSlot(bool)
    def __on_extent_toggle_dialog_visibility(self, visible: bool) -> None:
        """
        Shows or hides the dialog while the user is interactively
        defining an extent on the map canvas.

        This slot is connected to :py:signal:`QgsExtentWidget.toggleDialogVisibility`
        and is triggered when the extent widget enters or leaves the
        "Select extent on map" interaction mode.

        :param visible: Whether the dialog should be visible.
        :type visible: bool
        """
        if visible:
            self.show()
            self.raise_()
            self.activateWindow()
        else:
            self.hide()

    def __populate_output_format_combo_box(self) -> None:
        """
        Populate the output format combo box with supported tiles writer modes.
        """
        self.output_format_combo_box.clear()
        self.output_format_combo_box.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )

        writer_modes: Dict[TilesWriterMode, str] = {
            TilesWriterMode.DIR: self.tr("Directory"),
            TilesWriterMode.ZIP: self.tr("ZIP archive"),
            TilesWriterMode.MBTILES: self.tr("MBTiles"),
            TilesWriterMode.PMTILES: self.tr("PMTiles"),
            TilesWriterMode.NGM: self.tr("NextGIS Mobile"),
        }

        for writer_mode, label in writer_modes.items():
            self.output_format_combo_box.addItem(label, writer_mode)

            if writer_mode is TilesWriterMode.NGM:
                index: int = self.output_format_combo_box.count() - 1

                self.output_format_combo_box.setItemIcon(
                    index,
                    QIcon(":/plugins/qtiles/icons/ngm_logo.svg"),
                )

                font_metrics = self.output_format_combo_box.fontMetrics()
                icon_size = font_metrics.height()

                self.output_format_combo_box.setIconSize(
                    QSize(icon_size, icon_size)
                )

                self.output_format_combo_box.setItemData(
                    index,
                    self.tr("Archive format for NextGIS Mobile (.ngrc)"),
                    Qt.ItemDataRole.ToolTipRole,
                )

    def __configure_output_path_file_widget(
        self, writer_mode: TilesWriterMode
    ) -> None:
        """
        Configure output path file widget according to selected writer mode.

        :param writer_mode: Selected tiles writer mode.
        """
        self.output_path_file_widget.setFilePath("")

        if writer_mode.is_directory:
            self.output_path_file_widget.setStorageMode(
                QgsFileWidget.StorageMode.GetDirectory
            )
            self.output_path_file_widget.setFilter("")
        else:
            self.output_path_file_widget.setStorageMode(
                QgsFileWidget.StorageMode.SaveFile
            )
            self.output_path_file_widget.setFilter(
                writer_mode.file_dialog_filter or ""
            )
