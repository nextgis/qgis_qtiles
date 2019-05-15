# -*- coding: utf-8 -*-

# ******************************************************************************
#
# QTiles
# ---------------------------------------------------------
# Generates tiles from QGIS project
#
# Copyright (C) 2012-2014 NextGIS (info@nextgis.org)
# Copyright (C) 2019 Alexander Bruy (alexander.bruy@gmail.com)
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


import math

from qgis.core import QgsPointXY, QgsRectangle


class Tile:
    def __init__(self, x=0, y=0, z=0, tms=False):
        self.x = x
        self.y = y
        self.z = z
        self.tms = tms

    def toPoint(self):
        n = math.pow(2, self.z)
        if (self.tms):
            tms_f = -1
        else:
            tms_f = 1 
        longitude = float(self.x) / n * 360.0 - 180.0
        latitude = tms_f * math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * float(self.y) / n))))
        return QgsPointXY(longitude, latitude)

    def toRectangle(self):
        return QgsRectangle(self.toPoint(), Tile(self.x + 1, self.y + 1, self.z, self.tms).toPoint())

    def toExpandedRectangle(self):
        return QgsRectangle(Tile(self.x-1, self.y-1, self.z, self.tms).toPoint(),
                            Tile(self.x+2, self.y+2, self.z, self.tms).toPoint())
        
        
class TileLevelInfo:
    def __init__(self, zoomLevel, firstCol, firstRow, lastCol, lastRow):
        self.zoomLevel = zoomLevel
        self.firstCol = firstCol
        self.firstRow = firstRow
        self.lastCol = lastCol
        self.lastRow = lastRow
    
    
def tileFromLatLon(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return Tile(xtile, ytile, zoom)

