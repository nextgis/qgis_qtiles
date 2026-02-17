# -*- coding: utf-8 -*-

# ******************************************************************************
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
# ******************************************************************************


import math

from qgis.core import QgsPointXY, QgsRectangle


class Tile:
    """
    Representation of a single map tile in XYZ/TMS tiling scheme.
    """

    def __init__(
        self, x: int = 0, y: int = 0, z: int = 0, tms: int = 1
    ) -> None:
        """
        Create a tile definition.

        :param x: Tile X coordinate.
        :param y: Tile Y coordinate.
        :param z: Zoom level.
        :param tms: TMS orientation multiplier (1 or -1).
        """
        self.x = x
        self.y = y
        self.z = z
        self.tms = tms

    def to_point(self) -> QgsPointXY:
        """
        Convert tile coordinates to a geographic point (EPSG:4326).

        The point corresponds to the top-left corner of the tile.

        :return: Geographic point in WGS84.
        """
        n = math.pow(2, self.z)
        longitude = float(self.x) / n * 360.0 - 180.0
        latitude = self.tms * math.degrees(
            math.atan(math.sinh(math.pi * (1.0 - 2.0 * float(self.y) / n)))
        )
        return QgsPointXY(longitude, latitude)

    def to_rectangle(self) -> QgsRectangle:
        """
        Convert tile to a geographic rectangle (EPSG:4326).

        The rectangle covers the full extent of the tile.

        :return: Geographic rectangle in WGS84.
        """
        top_left = self.to_point()
        bottom_right = Tile(
            self.x + 1,
            self.y + 1,
            self.z,
            self.tms,
        ).to_point()

        return QgsRectangle(top_left, bottom_right)
