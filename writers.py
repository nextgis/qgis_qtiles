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

import sqlite3
import zipfile

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from mbutils import *


class DirectoryWriter:
    def __init__(self, outputPath, rootDir):
        self.output = outputPath
        self.rootDir = rootDir

    def writeTile(self, tile, image, format, quality):
        path = '%s/%s/%s' % (self.rootDir, tile.z, tile.x)
        dirPath = '%s/%s' % (self.output.absoluteFilePath(), path)
        QDir().mkpath(dirPath)
        image.save('%s/%s.%s' % (dirPath, tile.y, format.lower()), format, quality)

    def finalize(self):
        pass


class ZipWriter:
    def __init__(self, outputPath, rootDir):
        self.output = outputPath
        self.rootDir = rootDir

        self.zipFile = zipfile.ZipFile(unicode(self.output.absoluteFilePath()), 'w')
        self.tempFile = QTemporaryFile()
        self.tempFile.setAutoRemove(False)
        self.tempFile.open(QIODevice.WriteOnly)
        self.tempFileName = self.tempFile.fileName()
        self.tempFile.close()

    def writeTile(self, tile, image, format, quality):
        path = '%s/%s/%s' % (self.rootDir, tile.z, tile.x)

        image.save(self.tempFileName, format, quality)
        tilePath = '%s/%s.%s' % (path, tile.y, format.lower())
        self.zipFile.write(unicode(self.tempFileName), unicode(tilePath).encode('utf8'))

    def finalize(self):
        self.tempFile.close()
        self.tempFile.remove()
        self.zipFile.close()


class MBTilesWriter:

    def __init__(self, outputPath, rootDir, formatext, minZoom, maxZoom, extent, compression):
        self.output = outputPath
        self.rootDir = rootDir
        self.compression = compression
        s = str(extent.xMinimum()) + ',' + str(extent.yMinimum()) + ',' + str(extent.xMaximum()) + ','+ str(extent.yMaximum())
        self.connection = mbtiles_connect(unicode(self.output.absoluteFilePath()))
        self.cursor = self.connection.cursor()
        optimize_connection(self.cursor)
        mbtiles_setup(self.cursor)
        self.cursor.execute('''INSERT INTO metadata(name, value) VALUES (?, ?);''', ('name', rootDir))
        self.cursor.execute('''INSERT INTO metadata(name, value) VALUES (?, ?);''', ('description', 'Created with QTiles'))
        self.cursor.execute('''INSERT INTO metadata(name, value) VALUES (?, ?);''', ('format', formatext.lower()))
        self.cursor.execute('''INSERT INTO metadata(name, value) VALUES (?, ?);''', ('minZoom', str(minZoom)))
        self.cursor.execute('''INSERT INTO metadata(name, value) VALUES (?, ?);''', ('maxZoom', str(maxZoom)))
        self.cursor.execute('''INSERT INTO metadata(name, value) VALUES (?, ?);''', ('type', 'baselayer'))
        self.cursor.execute('''INSERT INTO metadata(name, value) VALUES (?, ?);''', ('version', '1.1'))
        self.cursor.execute('''INSERT INTO metadata(name, value) VALUES (?, ?);''', ('bounds', s))
        self.connection.commit()

    def writeTile(self, tile, image, format, quality):
        data = QByteArray()
        buff = QBuffer(data)
        image.save(buff, format, quality)

        self.cursor.execute('''INSERT INTO tiles(zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?);''', (tile.z, tile.x, tile.y, sqlite3.Binary(buff.data())))
        buff.close()

    def finalize(self):
        optimize_database(self.connection)
        self.connection.commit()
        if self.compression:
            # start compression
            compression_prepare(self.cursor, self.connection)
            self.cursor.execute("select count(zoom_level) from tiles")
            res = self.cursor.fetchone()
            total_tiles = res[0]
            compression_do(self.cursor, self.connection, total_tiles)
            compression_finalize(self.cursor)
            optimize_database(self.connection)
            self.connection.commit()
            # end compression
        self.connection.close()
        self.cursor = None
