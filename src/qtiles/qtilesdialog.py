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
    from qgis.gui import QgisInterface

from qgis.core import Qgis, QgsApplication, QgsMapLayer, QgsProject
from qgis.gui import QgsFileWidget, QgsGui
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QSize, Qt, pyqtSlot
from qgis.PyQt.QtGui import QCloseEvent, QIcon
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QSizePolicy,
    QToolButton,
)

from qtiles import qtiles_utils as utils
from qtiles.aboutdialog import AboutDialog
from qtiles.core.exceptions import TileGenerationWarning
from qtiles.core.settings import QTilesSettings
from qtiles.notifier.message_bar_notifier import MessageBarNotifier
from qtiles.restrictions import OpenStreetMapRestriction
from qtiles.tile import Tile
from qtiles.tilingthread import TilingThread
from qtiles.writers.enums import TilesWriterMode

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "ui/qtilesdialogbase.ui")
)


class QTilesDialog(QDialog, FORM_CLASS):
    """
    QTilesDialog is the main dialog for configuring
    and generating map tiles from a QGIS project.
    """

    def __init__(self, iface: "QgisInterface") -> None:
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

        self.notifier = MessageBarNotifier(self, self.message_bar)

        self.output_format_combo_box.currentIndexChanged.connect(
            self.__on_output_format_changed
        )

        self.extent_widget.toggleDialogVisibility.connect(
            self.__on_extent_toggle_dialog_visibility
        )

        self.button_run = self.buttonBox.addButton(
            self.tr("Run"), QDialogButtonBox.ButtonRole.ActionRole
        )
        self.button_run.clicked.connect(self._on_run_button_clicked)

        self.min_zoom_level_spinbox.value_changed.connect(
            self.__on_min_zoom_level_changed
        )

        self.max_zoom_level_spinbox.value_changed.connect(
            self.__on_max_zoom_level_changed
        )

        self.verticalLayout_2.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.work_thread = None

        self.button_close = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Close
        )

        self.cmbFormat.currentIndexChanged.connect(
            self._on_tile_image_format_changed
        )

        self.about_button.clicked.connect(self.__show_about)

        self.manageGui()

    def _on_run_button_clicked(self) -> None:
        """
        Start tile generation or cancel the running process.
        """
        if self.work_thread is not None and self.work_thread.isRunning():
            self.work_thread.stop()
            return

        self._run_tiling()

    def _on_tile_image_format_changed(self) -> None:
        """
        Update UI state according to selected tile image format.
        """
        is_jpg = self.cmbFormat.currentData() == "jpg"

        self.spnQuality.setEnabled(is_jpg)
        self.transparent_background_checkbox.setEnabled(not is_jpg)
        self.transparent_background_checkbox.setChecked(not is_jpg)

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

        preferred_policy = QSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        file_widget_line_edit.setSizePolicy(preferred_policy)

        self.output_path_file_widget.setConfirmOverwrite(False)
        file_widget_line_edit.setReadOnly(True)
        file_widget_line_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        file_widget_line_edit.setPlaceholderText(
            self.tr("Select output path…")
        )

        self._populate_output_format_combo_box()
        self._populate_tile_image_format_combo_data()

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

        self._load_settings_to_ui()

    def _load_settings_to_ui(self) -> None:
        """
        Load persisted plugin settings into UI widgets.
        """
        settings = QTilesSettings()

        tileset_name = settings.tileset_name
        if not tileset_name:
            project_name = QgsProject.instance().baseName()
            tileset_name = project_name if project_name else ""

        self.output_path_file_widget.setDefaultRoot(
            settings.last_output_dir + f"/{tileset_name}"
        )

        self.leRootDir.setText(tileset_name)

        self.output_format_combo_box.setCurrentIndex(
            settings.tiles_writer_mode
        )

        self.min_zoom_level_spinbox.set_value(settings.min_zoom)
        self.max_zoom_level_spinbox.set_value(settings.max_zoom)
        self.tile_size_spinbox.setValue(settings.tile_size)
        self.spinbox_dpi.setValue(settings.dpi)

        self.cmbFormat.setCurrentIndex(settings.tile_output_format)
        self.spnQuality.setValue(settings.jpg_quality)

        self.chkAntialiasing.setChecked(settings.enable_antialiasing)
        self.transparent_background_checkbox.setChecked(
            settings.transparent_background
        )
        self.chkRenderOutsideTiles.setChecked(settings.render_outside_tiles)
        self.chkTMSConvention.setChecked(settings.use_tms_convention)
        self.chkMBTilesCompression.setChecked(settings.use_mbtiles_compression)
        self.chkWriteJson.setChecked(settings.write_json_metadata)
        self.chkWriteOverview.setChecked(settings.write_overview)
        self.chkWriteMapurl.setChecked(settings.write_mapurl)
        self.chkWriteViewer.setChecked(settings.write_leaflet_viewer)

        self._on_tile_image_format_changed()

    @pyqtSlot()
    def __show_about(self) -> None:
        """
        Displays the About dialog for the QTiles plugin.
        """
        package_name = str(Path(__file__).parent.name)
        about_dialog = AboutDialog(package_name)
        about_dialog.exec()

    def _run_tiling(self) -> None:
        """
        Validates user input and starts the tile generation process.
        """
        self.notifier.dismiss_all()

        output_path_str = self.output_path_file_widget.filePath()

        if not output_path_str:
            self.notifier.dismiss_all()
            self.notifier.display_message(
                self.tr("Output path is not set. Please specify a path."),
                level=Qgis.MessageLevel.Warning,
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
        min_zoom = self.min_zoom_level_spinbox.value()
        max_zoom = self.max_zoom_level_spinbox.value()
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
            self.notifier.dismiss_all()
            self.notifier.display_message(
                self.tr(
                    "The current map extent does not intersect with the tiles. "
                    "Please check the extent and zoom level. "
                    "This could be caused by an invalid or out-of-bounds extent."
                ),
                level=Qgis.MessageLevel.Warning,
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

        self.work_thread = TilingThread(
            tiles,
            layers,
            writer_mode,
            target_extent,
            min_zoom,
            max_zoom,
            self.tile_size_spinbox.value(),
            self.spnQuality.value(),
            self.spinbox_dpi.value(),
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

        self.work_thread.rangeChanged.connect(self.setProgressRange)
        self.work_thread.updateProgress.connect(self.updateProgress)
        self.work_thread.processFinished.connect(self.processFinished)
        self.work_thread.processInterrupted.connect(self.processInterrupted)
        self.work_thread.processError.connect(self.processError)
        self.button_run.setText(self.tr("Cancel"))
        self.progressBar.setVisible(True)
        self.work_thread.start()

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
        self.stopProcessingAndCleanupResults()

        self.notifier.dismiss_all()
        self.notifier.display_message(
            self.tr("Tile generation was cancelled."),
            level=Qgis.MessageLevel.Warning,
        )

        self.restoreGui()

    @pyqtSlot()
    def processFinished(self) -> None:
        """
        Restores the GUI state and stops
        the tile generation process when it is completed.
        """
        work_thread = self.work_thread
        warning = work_thread.warning if work_thread is not None else None

        self._finalize_processing(cleanup_output=False)

        if isinstance(warning, TileGenerationWarning):
            self.notifier.dismiss_all()
            self.notifier.display_message(
                warning.user_message,
                level=Qgis.MessageLevel.Warning,
            )
        else:
            self.notifier.dismiss_all()
            self.notifier.display_message(
                self.tr("Tile generation completed successfully."),
                level=Qgis.MessageLevel.Success,
            )

        self.restoreGui()

    @pyqtSlot()
    def processError(self) -> None:
        """
        Restores the GUI state and reports a tile generation error.
        """
        work_thread = self.work_thread

        self.stopProcessingAndCleanupResults()
        self.restoreGui()

        if work_thread is None or work_thread.error is None:
            return

        self.notifier.dismiss_all()
        self.notifier.display_exception(work_thread.error)

    def stopProcessingAndCleanupResults(self) -> None:
        """
        Stops the tile generation process and removes incomplete output.
        """
        self._finalize_processing(cleanup_output=True)

    def _finalize_processing(self, cleanup_output: bool) -> None:
        """
        Stops the tile generation process if it is running.

        :param cleanup_output: Whether incomplete output should be removed.
        """
        if self.work_thread is None:
            return

        if self.work_thread.isRunning():
            self.work_thread.stop()

        self.work_thread = None

        if cleanup_output:
            self._cleanup_incomplete_tileset()

    def restoreGui(self) -> None:
        """
        Restores the initial GUI state
        after a process has finished or been interrupted.
        """
        self.progressBar.setFormat("%p%")
        self.progressBar.setRange(0, 1)
        self.progressBar.setValue(0)
        self.progressBar.setVisible(False)

        self.button_run.setText(self.tr("Run"))

    def reject(self) -> None:
        """
        Handle dialog close requests.

        :param event: Qt close event instance.
        """
        if self.work_thread is None or not self.work_thread.isRunning():
            super().reject()
            return

        reply = QMessageBox.question(
            self,
            self.tr("Tile generation in progress"),
            self.tr(
                "Tile generation is still running.\n"
                "Do you want to cancel it and close the dialog?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.stopProcessingAndCleanupResults()
        super().reject()

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
            self.chkWriteOverview.setChecked(False)
            self.chkWriteOverview.setEnabled(False)

            self.chkWriteJson.setChecked(False)
            self.chkWriteJson.setEnabled(False)

    @pyqtSlot(int)
    def __on_min_zoom_level_changed(self, min_zoom_level: int) -> None:
        """
        Synchronizes the maximum zoom level spin box when the minimum zoom level changes.

        Ensures that the invariant ``min_zoom_level <= max_zoom_level`` is preserved.
        The maximum zoom level spin box minimum boundary is updated to match the
        new minimum zoom level. If the current maximum zoom level is lower than
        the updated minimum, it is automatically adjusted to the same value.

        :param min_zoom_level: The newly selected minimum zoom level.

        :return: None
        """
        max_zoom_level = self.max_zoom_level_spinbox.value()

        self.max_zoom_level_spinbox.set_minimum(min_zoom_level)

        if min_zoom_level > max_zoom_level:
            self.max_zoom_level_spinbox.set_value(min_zoom_level)

    @pyqtSlot(int)
    def __on_max_zoom_level_changed(self, max_zoom_level: int) -> None:
        """
        Synchronizes the minimum zoom level spin box when the maximum zoom level changes.

        Ensures that the invariant ``min_zoom_level <= max_zoom_level`` is preserved.
        The minimum zoom level spin box maximum boundary is updated to match the
        new maximum zoom level. If the current minimum zoom level exceeds
        the updated maximum, it is automatically adjusted to the same value.

        :param max_zoom_level: The newly selected maximum zoom level.
        :type max_zoom_level: int
        :return: None
        """
        min_zoom_level = self.min_zoom_level_spinbox.value()

        self.min_zoom_level_spinbox.set_maximum(max_zoom_level)

        if min_zoom_level > max_zoom_level:
            self.min_zoom_level_spinbox.set_value(max_zoom_level)

    def __is_input_parameters_valid(self) -> bool:
        """
        Validate user-provided input parameters before starting tile generation.

        :return: ``True`` if all input parameters are valid, ``False`` otherwise.
        """
        if not self.extent_widget.isValid():
            self.notifier.dismiss_all()
            self.notifier.display_message(
                self.tr("Please specify a valid map extent."),
                level=Qgis.MessageLevel.Warning,
            )
            return False

        min_zoom = self.min_zoom_level_spinbox.value()
        max_zoom = self.max_zoom_level_spinbox.value()
        if min_zoom > max_zoom:
            self.notifier.dismiss_all()
            self.notifier.display_message(
                self.tr(
                    "Maximum zoom value is lower than minimum. Please correct this and try again."
                ),
                level=Qgis.MessageLevel.Warning,
            )
            return False

        return True

    def __save_settings(self) -> None:
        """
        Persist current dialog state to plugin settings.
        """
        settings = QTilesSettings()

        path = Path(self.output_path_file_widget.filePath())

        if path.suffix:
            settings.last_output_dir = str(path.parent)
        else:
            settings.last_output_dir = str(path)

        settings.tileset_name = self.leRootDir.text()
        settings.tiles_writer_mode = (
            self.output_format_combo_box.currentIndex()
        )
        settings.min_zoom = self.min_zoom_level_spinbox.value()
        settings.max_zoom = self.max_zoom_level_spinbox.value()
        settings.tile_size = self.tile_size_spinbox.value()
        settings.dpi = self.spinbox_dpi.value()
        settings.tile_output_format = self.cmbFormat.currentIndex()
        settings.jpg_quality = self.spnQuality.value()
        settings.enable_antialiasing = self.chkAntialiasing.isChecked()
        settings.transparent_background = (
            self.transparent_background_checkbox.isChecked()
        )
        settings.render_outside_tiles = self.chkRenderOutsideTiles.isChecked()
        settings.use_tms_convention = self.chkTMSConvention.isChecked()
        settings.use_mbtiles_compression = (
            self.chkMBTilesCompression.isChecked()
        )
        settings.write_json_metadata = self.chkWriteJson.isChecked()
        settings.write_overview = self.chkWriteOverview.isChecked()
        settings.write_mapurl = self.chkWriteMapurl.isChecked()
        settings.write_leaflet_viewer = self.chkWriteViewer.isChecked()

        self._load_settings_to_ui()

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
            self.notifier.dismiss_all()
            self.notifier.display_message(
                message,
                level=Qgis.MessageLevel.Warning,
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
            self.notifier.dismiss_all()
            self.notifier.display_message(
                self.tr(
                    "Failed to overwrite {desc}:\n{path}\n\nError: {err}"
                ).format(
                    desc=description, path=str(output_path), err=str(error)
                ),
                level=Qgis.MessageLevel.Critical,
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
            self.notifier.dismiss_all()
            self.notifier.display_message(
                self.tr(
                    "Tileset name cannot be empty. Please specify a name."
                ),
                level=Qgis.MessageLevel.Warning,
            )
            return False

        if tileset_name in forbidden_names or any(
            char in tileset_name for char in forbidden_chars
        ):
            self.notifier.dismiss_all()
            self.notifier.display_message(
                self.tr(
                    "Tileset name contains forbidden characters or reserved names. "
                    "Please choose a different name."
                ),
                level=Qgis.MessageLevel.Warning,
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

    def _populate_output_format_combo_box(self) -> None:
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
            self._add_output_format_item(writer_mode, label)

    def _add_output_format_item(
        self,
        writer_mode: TilesWriterMode,
        label: str,
    ) -> None:
        """
        Add a single output format item to the combo box
        with optional per-mode customization.
        """
        combo_box = self.output_format_combo_box
        combo_box.addItem(label, writer_mode)

        if writer_mode is TilesWriterMode.NGM:
            index: int = combo_box.count() - 1

            combo_box.setItemIcon(
                index,
                QIcon(":/plugins/qtiles/icons/ngm_logo.svg"),
            )

            font_metrics = combo_box.fontMetrics()
            icon_size = font_metrics.height()

            combo_box.setIconSize(QSize(icon_size, icon_size))

            combo_box.setItemData(
                index,
                self.tr("Archive format for NextGIS Mobile (.ngrc)"),
                Qt.ItemDataRole.ToolTipRole,
            )

    def _populate_tile_image_format_combo_data(self) -> None:
        """
        Populate tile image format combo box with stable text and item data.
        """
        tile_image_formats = (
            ("PNG", "png"),
            ("JPG", "jpg"),
        )

        for text, data in tile_image_formats:
            self.cmbFormat.addItem(text, data)

    def __configure_output_path_file_widget(
        self, writer_mode: TilesWriterMode
    ) -> None:
        """
        Configure output path file widget according to selected writer mode.

        :param writer_mode: Selected tiles writer mode.
        """
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

        current_path_str = self.output_path_file_widget.filePath()
        if not current_path_str:
            return

        current_path = Path(current_path_str)
        mode_extension = writer_mode.file_extension

        new_path = current_path.with_suffix(f"{mode_extension}")
        self.output_path_file_widget.setFilePath(str(new_path))

    def _cleanup_incomplete_tileset(self) -> None:
        """
        Remove incomplete tileset output if generation was cancelled.

        Shows a notification only if cleanup fails.
        """
        writer_mode: Optional[TilesWriterMode] = (
            self.output_format_combo_box.currentData()
        )

        if writer_mode is None:
            return

        output_path_str = self.output_path_file_widget.filePath()
        if not output_path_str:
            return

        output_path = Path(output_path_str)
        tileset_name = self.leRootDir.text()

        if writer_mode.is_directory:
            target_path = output_path / tileset_name
        else:
            target_path = output_path

        if not target_path.exists():
            return

        try:
            if target_path.is_dir():
                shutil.rmtree(target_path)
            else:
                target_path.unlink()

        except Exception as error:
            self.notifier.dismiss_all()
            self.notifier.display_message(
                self.tr(
                    "Failed to remove incomplete tileset:\n{path}\n\nError: {error}"
                ).format(
                    path=str(target_path),
                    error=str(error),
                ),
                level=Qgis.MessageLevel.Warning,
            )
