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

from PyQt4.QtCore import *

from qgis.core import *

def getMapLayers():
  layerMap = QgsMapLayerRegistry.instance().mapLayers()
  layers = dict()
  for name, layer in layerMap.iteritems():
    if layer.type() == QgsMapLayer.VectorLayer:
      if layer.id() not in layers.keys():
        layers[layer.id()] = unicode(layer.name())
    if (layer.type() == QgsMapLayer.RasterLayer and layer.providerType() == "gdal"):
      if layer.id() not in layers.keys():
        layers[layer.id()] = unicode(layer.name())
  return layers

def getLayerById(layerId):
  layerMap = QgsMapLayerRegistry.instance().mapLayers()
  for name, layer in layerMap.iteritems():
    if layer.id() == layerId:
      if layer.isValid():
        return layer
      else:
        return None

def getLayerGroup(relations, layerId):
  group = None

  for item in relations:
    group = unicode(item[0])
    for lid in item[1]:
      if unicode(lid) == unicode(layerId):
        return group

  return group
