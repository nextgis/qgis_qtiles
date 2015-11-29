# -*- coding: utf-8 -*-

#******************************************************************************
#
# QTiles
# ---------------------------------------------------------
# Generates tiles from QGIS project
#
# Copyright (C) 2012-2014 NextGIS (info@nextgis.org)
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
#******************************************************************************
import locale
import math
import operator
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
import tilingthread
from ui.ui_qtilesdialogbase import Ui_Dialog
import qtiles_utils as utils


class QTilesDialog(QDialog, Ui_Dialog):
    MAX_ZOOM_LEVEL = 18
    MIN_ZOOM_LEVEL = 0

    def __init__(self, iface):
        QDialog.__init__(self)
        self.setupUi(self)

        self.spnZoomMax.setMaximum(self.MAX_ZOOM_LEVEL)
        self.spnZoomMax.setMinimum(self.MIN_ZOOM_LEVEL)
        self.spnZoomMin.setMaximum(self.MAX_ZOOM_LEVEL)
        self.spnZoomMin.setMinimum(self.MIN_ZOOM_LEVEL)

        self.spnZoomMin.valueChanged.connect(self.spnZoomMax.setMinimum)
        self.spnZoomMax.valueChanged.connect(self.spnZoomMin.setMaximum)

        self.iface = iface

        self.verticalLayout_2.setAlignment(Qt.AlignTop)

        self.workThread = None

        self.FORMATS = {
            self.tr('ZIP archives (*.zip *.ZIP)'): '.zip',
            self.tr('MBTiles databases (*.mbtiles *.MBTILES)'): '.mbtiles'}

        self.settings = QSettings('NextGIS', 'QTiles')
        self.grpParameters.setSettings(self.settings)
        self.btnOk = self.buttonBox.button(QDialogButtonBox.Ok)
        self.btnClose = self.buttonBox.button(QDialogButtonBox.Close)
        self.rbExtentLayer.toggled.connect(self.__toggleLayerSelector)
        self.chkLockRatio.stateChanged.connect(self.__toggleHeightEdit)
        self.spnTileWidth.valueChanged.connect(self.__updateTileSize)
        self.btnBrowse.clicked.connect(self.__select_output)
        self.cmbFormat.activated.connect(self.formatChanged)

        self.rbOutputZip.toggled.connect(self.__toggleTarget)
        self.rbOutputDir.toggled.connect(self.__toggleTarget)
        self.rbOutputNGM.toggled.connect(self.__toggleTarget)
        self.rbOutputNGM.setIcon(QIcon(':/icons/ngm_index_24x24.png'))

        self.lInfoIconOutputZip.linkActivated.connect(self.show_output_info)
        self.lInfoIconOutputDir.linkActivated.connect(self.show_output_info)
        self.lInfoIconOutputNGM.linkActivated.connect(self.show_output_info)

        self.manageGui()

    def show_output_info(self, href):
        title = self.tr("Output type info")
        message = ""
        if self.sender() is self.lInfoIconOutputZip:
            message = self.tr("Save tiles as Zip or MBTiles")
        elif self.sender() is self.lInfoIconOutputDir:
            message = self.tr("Save tiles as directory structure")
        elif self.sender() is self.lInfoIconOutputNGM:
            message = "<table cellspacing='10'> <tr> \
                        <td> \
                            <img src=':/icons/ngm_index_24x24.png'/> \
                        </td> \
                        <td> \
                            Prepare package for <a href='http://nextgis.ru/en/nextgis-mobile/'> NextGIS Mobile </a> \
                        </td> \
                    </tr> </table>"

        # QMessageBox.information(
        #     self,
        #     title,
        #     message
        # )
        msgBox = QMessageBox()
        msgBox.setWindowTitle(title)
        msgBox.setText(message)
        msgBox.exec_()

    def formatChanged(self):
        if self.cmbFormat.currentText() == 'JPG':
            self.spnTransparency.setEnabled(False)
            self.spnQuality.setEnabled(True)
        else:
            self.spnTransparency.setEnabled(True)
            self.spnQuality.setEnabled(False)

    def manageGui(self):
        layers = utils.getMapLayers()
        relations = self.iface.legendInterface().groupLayerRelationship()
        for layer in sorted(layers.iteritems(), cmp=locale.strcoll, key=operator.itemgetter(1)):
            groupName = utils.getLayerGroup(relations, layer[0])
            if groupName == '':
                self.cmbLayers.addItem(layer[1], layer[0])
            else:
                self.cmbLayers.addItem('%s - %s' % (layer[1], groupName), layer[0])

        self.rbOutputZip.setChecked(self.settings.value('outputToZip', True, type=bool))
        self.rbOutputDir.setChecked(self.settings.value('outputToDir', False, type=bool))
        self.rbOutputNGM.setChecked(self.settings.value('outputToNGM', False, type=bool))
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

        self.leZipFileName.setText(self.settings.value('outputToZip_Path', ''))
        self.leDirectoryName.setText(self.settings.value('outputToDir_Path', ''))
        self.leTilesFroNGM.setText(self.settings.value('outputToNGM_Path', ''))

        self.cmbLayers.setEnabled(False)
        self.leRootDir.setText(self.settings.value('rootDir', 'Mapnik'))
        self.rbExtentCanvas.setChecked(self.settings.value('extentCanvas', True, type=bool))
        self.rbExtentFull.setChecked(self.settings.value('extentFull', False, type=bool))
        self.rbExtentLayer.setChecked(self.settings.value('extentLayer', False, type=bool))
        self.spnZoomMin.setValue(self.settings.value('minZoom', 0, type=int))
        self.spnZoomMax.setValue(self.settings.value('maxZoom', 18, type=int))
        self.chkLockRatio.setChecked(self.settings.value('keepRatio', True, type=bool))
        self.spnTileWidth.setValue(self.settings.value('tileWidth', 256, type=int))
        self.spnTileHeight.setValue(self.settings.value('tileHeight', 256, type=int))
        self.spnTransparency.setValue(self.settings.value('transparency', 255, type=int))
        self.spnQuality.setValue(self.settings.value('quality', 70, type=int))
        self.cmbFormat.setCurrentIndex(int(self.settings.value('format', 0)))
        self.chkAntialiasing.setChecked(self.settings.value('enable_antialiasing', False, type=bool))
        self.chkTMSConvention.setChecked(self.settings.value('use_tms_filenames', False, type=bool))
        self.chkMBTilesCompression.setChecked(self.settings.value('use_mbtiles_compression', False, type=bool))
        self.chkWriteJson.setChecked(self.settings.value("write_json", False, type=bool))
        self.chkWriteOverview.setChecked(self.settings.value("write_overview", False, type=bool))
        self.chkWriteMapurl.setChecked(self.settings.value("write_mapurl", False, type=bool))
        self.chkWriteViewer.setChecked(self.settings.value("write_viewer", False, type=bool))

        self.formatChanged()

    def reject(self):
        QDialog.reject(self)

    def accept(self):
        if self.rbOutputZip.isChecked():
            output = self.leZipFileName.text()
        elif self.rbOutputDir.isChecked():
            output = self.leDirectoryName.text()
        elif self.rbOutputNGM.isChecked():
            output = self.leTilesFroNGM.text()

        if not output:
            QMessageBox.warning(self, self.tr('No output'), self.tr('Output path is not set. Please enter correct path and try again.'))
            return
        fileInfo = QFileInfo(output)
        if fileInfo.isDir() and not len(QDir(output).entryList(QDir.Dirs | QDir.Files | QDir.NoDotAndDotDot)) == 0:
            res = QMessageBox.warning(self, self.tr('Directory not empty'), self.tr('Selected directory is not empty. Continue?'), QMessageBox.Yes | QMessageBox.No)
            if res == QMessageBox.No:
                return
        if self.spnZoomMin.value() > self.spnZoomMax.value():
            QMessageBox.warning(self, self.tr('Wrong zoom'), self.tr('Maximum zoom value is lower than minimum. Please correct this and try again.'))
            return
        self.settings.setValue('rootDir', self.leRootDir.text())
        self.settings.setValue('outputToZip', self.rbOutputZip.isChecked())
        self.settings.setValue('outputToDir', self.rbOutputDir.isChecked())
        self.settings.setValue('outputToNGM', self.rbOutputNGM.isChecked())
        self.settings.setValue('extentCanvas', self.rbExtentCanvas.isChecked())
        self.settings.setValue('extentFull', self.rbExtentFull.isChecked())
        self.settings.setValue('extentLayer', self.rbExtentLayer.isChecked())
        self.settings.setValue('minZoom', self.spnZoomMin.value())
        self.settings.setValue('maxZoom', self.spnZoomMax.value())
        self.settings.setValue('keepRatio', self.chkLockRatio.isChecked())
        self.settings.setValue('tileWidth', self.spnTileWidth.value())
        self.settings.setValue('tileHeight', self.spnTileHeight.value())
        self.settings.setValue('format', self.cmbFormat.currentIndex())
        self.settings.setValue('transparency', self.spnTransparency.value())
        self.settings.setValue('quality', self.spnQuality.value())
        self.settings.setValue('enable_antialiasing', self.chkAntialiasing.isChecked())
        self.settings.setValue('use_tms_filenames', self.chkTMSConvention.isChecked())
        self.settings.setValue('use_mbtiles_compression', self.chkMBTilesCompression.isChecked())
        self.settings.setValue('write_json', self.chkWriteJson.isChecked())
        self.settings.setValue('write_overview', self.chkWriteOverview.isChecked())
        self.settings.setValue('write_mapurl', self.chkWriteMapurl.isChecked())
        self.settings.setValue('write_viewer', self.chkWriteViewer.isChecked())
        canvas = self.iface.mapCanvas()
        if self.rbExtentCanvas.isChecked():
            extent = canvas.extent()
        elif self.rbExtentFull.isChecked():
            extent = canvas.fullExtent()
        else:
            layer = utils.getLayerById(self.cmbLayers.itemData(self.cmbLayers.currentIndex()))
            extent = canvas.mapRenderer().layerExtentToOutputExtent(layer, layer.extent())
        extent = QgsCoordinateTransform(canvas.mapRenderer().destinationCrs(), QgsCoordinateReferenceSystem('EPSG:4326')).transform(extent)
        arctanSinhPi = math.degrees(math.atan(math.sinh(math.pi)))
        extent = extent.intersect(QgsRectangle(-180, -arctanSinhPi, 180, arctanSinhPi))
        layers = canvas.mapSettings().layers()
        writeMapurl = self.chkWriteMapurl.isEnabled() and self.chkWriteMapurl.isChecked()
        writeViewer = self.chkWriteViewer.isEnabled() and self.chkWriteViewer.isChecked()
        self.workThread = tilingthread.TilingThread(
            layers,
            extent,
            self.spnZoomMin.value(),
            self.spnZoomMax.value(),
            self.spnTileWidth.value(),
            self.spnTileHeight.value(),
            self.spnTransparency.value(),
            self.spnQuality.value(),
            self.cmbFormat.currentText(),
            fileInfo,
            self.leRootDir.text(),
            self.chkAntialiasing.isChecked(),
            self.chkTMSConvention.isChecked(),
            self.chkMBTilesCompression.isChecked(),
            self.chkWriteJson.isChecked(),
            self.chkWriteOverview.isChecked(),
            writeMapurl,
            writeViewer
        )

        self.workThread.rangeChanged.connect(self.setProgressRange)
        self.workThread.updateProgress.connect(self.updateProgress)
        self.workThread.processFinished.connect(self.processFinished)
        self.workThread.processInterrupted.connect(self.processInterrupted)
        self.btnOk.setEnabled(False)
        self.btnClose.setText(self.tr('Cancel'))
        self.buttonBox.rejected.disconnect(self.reject)
        self.btnClose.clicked.connect(self.stopProcessing)
        self.workThread.start()
    def setProgressRange(self, message, value):
        self.progressBar.setFormat(message)
        self.progressBar.setRange(0, value)
    def updateProgress(self):
        self.progressBar.setValue(self.progressBar.value() + 1)
    def processInterrupted(self):
        self.restoreGui()
    def processFinished(self):
        self.stopProcessing()
        self.restoreGui()
    def stopProcessing(self):
        if self.workThread is not None:
            self.workThread.stop()
            self.workThread = None
    def restoreGui(self):
        self.progressBar.setFormat('%p%')
        self.progressBar.setRange(0, 1)
        self.progressBar.setValue(0)
        self.buttonBox.rejected.connect(self.reject)
        self.btnClose.clicked.disconnect(self.stopProcessing)
        self.btnClose.setText(self.tr('Close'))
        self.btnOk.setEnabled(True)

    def __toggleTarget(self, checked):
        if checked:
            if self.sender() is self.rbOutputZip:
                self.leZipFileName.setEnabled(True)
                self.leDirectoryName.setEnabled(False)
                self.leTilesFroNGM.setEnabled(False)
                self.chkWriteMapurl.setEnabled(False)
                self.chkWriteViewer.setEnabled(False)

                self.spnTileWidth.setEnabled(True)
                self.chkLockRatio.setEnabled(True)
                self.cmbFormat.setEnabled(True)
            elif self.sender() is self.rbOutputDir:
                self.leZipFileName.setEnabled(False)
                self.leDirectoryName.setEnabled(True)
                self.leTilesFroNGM.setEnabled(False)
                self.chkWriteMapurl.setEnabled(True)
                self.chkWriteViewer.setEnabled(True)

                self.spnTileWidth.setEnabled(True)
                self.chkLockRatio.setEnabled(True)
                self.cmbFormat.setEnabled(True)
            elif self.sender() is self.rbOutputNGM:
                self.leZipFileName.setEnabled(False)
                self.leDirectoryName.setEnabled(False)
                self.leTilesFroNGM.setEnabled(True)
                self.chkWriteMapurl.setEnabled(False)
                self.chkWriteViewer.setEnabled(False)

                self.spnTileWidth.setValue(256)
                self.spnTileWidth.setEnabled(False)
                self.chkLockRatio.setCheckState(Qt.Checked)
                self.chkLockRatio.setEnabled(False)
                self.cmbFormat.setCurrentIndex(0)
                self.cmbFormat.setEnabled(False)

    def __toggleLayerSelector(self, checked):
        self.cmbLayers.setEnabled(checked)

    def __toggleHeightEdit(self, state):
        if state == Qt.Checked:
            self.lblHeight.setEnabled(False)
            self.spnTileHeight.setEnabled(False)
            self.spnTileHeight.setValue(self.spnTileWidth.value())
        else:
            self.lblHeight.setEnabled(True)
            self.spnTileHeight.setEnabled(True)

    @pyqtSlot(int)
    def __updateTileSize(self, value):
        if self.chkLockRatio.isChecked():
            self.spnTileHeight.setValue(value)

    def __select_output(self):
        if self.rbOutputZip.isChecked():
            file_directory = QFileInfo(self.settings.value('outputToZip_Path', '.')).absolutePath()
            outPath, outFilter = QFileDialog.getSaveFileNameAndFilter(self, self.tr('Save to file'), file_directory, ';;'.join(self.FORMATS.iterkeys()), self.FORMATS.keys()[self.FORMATS.values().index('.zip')])
            if not outPath:
                return
            if not outPath.lower().endswith(self.FORMATS[outFilter]):
                outPath += self.FORMATS[outFilter]
            self.leZipFileName.setText(outPath)
            self.settings.setValue('outputToZip_Path', QFileInfo(outPath).absoluteFilePath())

        elif self.rbOutputDir.isChecked():
            dir_directory = QFileInfo(self.settings.value('outputToDir_Path', '.')).absolutePath()
            outPath = QFileDialog.getExistingDirectory(self, self.tr('Save to directory'), dir_directory, QFileDialog.ShowDirsOnly)
            if not outPath:
                return
            self.leDirectoryName.setText(outPath)
            self.settings.setValue('outputToDir_Path', QFileInfo(outPath).absoluteFilePath())

        elif self.rbOutputNGM.isChecked():
            zip_directory = QFileInfo(self.settings.value('outputToNGM_Path', '.')).absolutePath()
            outPath, outFilter = QFileDialog.getSaveFileNameAndFilter(self, self.tr('Save to file'), zip_directory, 'ngrc')
            if not outPath:
                return
            if not outPath.lower().endswith('ngrc'):
                outPath += '.ngrc'
            self.leTilesFroNGM.setText(outPath)
            self.settings.setValue('outputToNGM_Path', QFileInfo(outPath).absoluteFilePath())
