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

def name():
  return "QTiles"

def description():
  return "Generate tiles from QGIS project"

def category():
  return "Plugins"

def version():
  return "1.0.0"

def qgisMinimumVersion():
  return "1.9.0"

def author():
  return "Alexander Bruy (NextGIS)"

def email():
  return "alexander.bruy@gmail.com"

def icon():
  return "icons/qtiles.png"

def classFactory( iface ):
  from qtiles import QTilesPlugin
  return QTilesPlugin( iface )
