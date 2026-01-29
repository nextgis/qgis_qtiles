# -*- coding: utf-8 -*-

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
import math
from typing import List, Optional

from qgis.core import (
    QgsMapLayer,
    QgsRectangle,
)

from qtiles.compat import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
)
from qtiles.tile import Tile

TILES_COUNT_TRESHOLD = 10000


def compute_target_extent(extent: QgsRectangle) -> QgsRectangle:
    """
    Clamps a WGS84 extent to valid Web Mercator geographic bounds.

    :param extent: The geographic extent to clamp.
    :type extent: QgsRectangle

    :return: The clamped extent within valid geographic bounds.
    :rtype: QgsRectangle
    """
    arctan_sinh_pi = math.degrees(math.atan(math.sinh(math.pi)))
    return extent.intersect(
        QgsRectangle(-180, -arctan_sinh_pi, 180, arctan_sinh_pi)
    )


def count_tiles(
    tile: Tile,
    layers: List[QgsMapLayer],
    extent: QgsRectangle,
    min_zoom: int,
    max_zoom: int,
    render_outside_tiles: bool,
) -> Optional[List[Tile]]:
    """
    Recursively counts the number of tiles to be generated.

    This method calculates the tiles required for the specified extent
    and zoom levels. It supports rendering tiles outside the map extent
    if enabled.

    :param tile: The initial tile to start counting from.
    :param layers: A list of map layers to consider for tile generation.
    :param extent: The geographical extent for tile generation.
    :param min_zoom: The minimum zoom level.
    :param max_zoom: The maximum zoom level.
    :param render_outside_tiles: Whether to include tiles outside themap extent.

    :returns: A list of tiles to be generated or None if no tiles are required.
    """
    tile_extent = tile.toRectangle()
    if not extent.intersects(tile.toRectangle()):
        return None

    tiles = []
    if min_zoom <= tile.z <= max_zoom:
        if not render_outside_tiles:
            for layer in layers:
                crs_transform = QgsCoordinateTransform(
                    layer.crs(),
                    QgsCoordinateReferenceSystem.fromEpsgId(4326),
                )
                if crs_transform.transform(layer.extent()).intersects(
                    tile_extent
                ):
                    tiles.append(tile)
                    break
        else:
            tiles.append(tile)
    if tile.z < max_zoom:
        for x in (2 * tile.x, 2 * tile.x + 1):
            for y in (2 * tile.y, 2 * tile.y + 1):
                sub_tile = Tile(x, y, tile.z + 1, tile.tms)
                sub_tiles = count_tiles(
                    sub_tile,
                    layers,
                    extent,
                    min_zoom,
                    max_zoom,
                    render_outside_tiles,
                )
                if sub_tiles:
                    tiles.extend(sub_tiles)

    return tiles
