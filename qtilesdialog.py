# -*- coding: utf-8 -*-

#******************************************************************************
#
# QTiles
# ---------------------------------------------------------
# Generates tiles from QGIS project
#
# Copyright (C) 2012 Alexander Bruy (alexander.bruy@gmail.com)
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
import operator

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from qgis.core import *

from ui_qtilesdialogbase import Ui_Dialog

import qtiles_utils as utils

class QTilesDialog(QDialog, Ui_Dialog):
  def __init__(self, iface):
    QDialog.__init__(self)
    self.setupUi(self)

    self.iface = iface
    self.workThread = None

    self.btnOk = self.buttonBox.button(QDialogButtonBox.Ok)
    self.btnClose = self.buttonBox.button(QDialogButtonBox.Close)

    self.rbOutputZip.toggled.connect(self.__toggleZipTarget)
    self.rbExtentLayer.toggled.connect(self.__toggleLayerSelector)
    self.chkLockRatio.stateChanged.connect(self.__toggleHeightEdit)
    self.spnTileWidth.valueChanged.connect(self.__updateTileSize)

    self.manageGui()

  def manageGui(self):
    # populate combobox with layers
    layers = utils.getMapLayers()
    relations = self.iface.legendInterface().groupLayerRelationship()
    for layer in sorted(layers.iteritems(), cmp=locale.strcoll, key=operator.itemgetter(1)):
      groupName = utils.getLayerGroup(relations, layer[0])
      if groupName is None:
        self.cmbLayers.addItem(layer[1], layer[0])
      else:
        self.cmbLayers.addItem(QString("%1 - %2").arg(layer[1]).arg(groupName), layer[0])

    # restore ui state from settings
    settings = QSettings("NextGIS", "QTiles")

    self.rbOutputZip.setChecked(settings.value("outputToZip", True).toBool())
    self.rbOutputDir.setChecked(settings.value("outputToDir", False).toBool())

    if self.rbOutputZip.isChecked():
      self.leDirectoryName.setEnabled(False)
    else:
      self.leZipFileName.setEnabled(False)

    self.rbExtentCanvas.setChecked(settings.value("extentCanvas", True).toBool())
    self.rbExtentFull.setChecked(settings.value("extentFull", False).toBool())
    self.rbExtentLayer.setChecked(settings.value("extentLayer", False).toBool())

    self.spnZoomMin.setValue(settings.value("minZoom", 0).toInt()[0])
    self.spnZoomMax.setValue(settings.value("maxZoom", 18).toInt()[0])

    self.chkLockRatio.setChecked(settings.value("keepRatio", True).toBool())
    self.spnTileWidth.setValue(settings.value("tileWidth", 256).toInt()[0])
    self.spnTileHeight.setValue(settings.value("tileHeight", 256).toInt()[0])

  def reject(self):
    QDialog.reject(self)

  def accept(self):
    settings = QSettings("NextGIS", "QTiles")

    settings.setValue("outputToZip", self.rbOutputZip.isChecked())
    settings.setValue("outputToDir", self.rbOutputDir.isChecked())

    settings.setValue("extentCanvas", self.rbExtentCanvas.isChecked())
    settings.setValue("extentFull", self.rbExtentFull.isChecked())
    settings.setValue("extentLayer", self.rbExtentLayer.isChecked())

    settings.setValue("minZoom", self.spnZoomMin.value())
    settings.setValue("maxZoom", self.spnZoomMax.value())

    settings.setValue("keepRatio", self.chkLockRatio.isChecked())
    settings.setValue("tileWidth", self.spnTileWidth.value())
    settings.setValue("tileHeight", self.spnTileHeight.value())

    QDialog.accept(self)

  def __toggleZipTarget(self, checked):
    self.leZipFileName.setEnabled(checked)
    self.leDirectoryName.setEnabled(not checked)

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
