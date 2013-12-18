# -*- coding: utf-8 -*-

"""
***************************************************************************
    writers.py
    ---------------------
    Date                 : December 2013
    Copyright            : (C) 2013 by Alexander Bruy
    Email                : alexander dot bruy at gmail dot com
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

__author__ = 'Alexander Bruy'
__date__ = 'December 2013'
__copyright__ = '(C) 2013, Alexander Bruy'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import os
import sqlite3
import zipfile

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from mbutils import *


class DirectoryWriter:
    def __init__(self, outputPath, rootDir):
        self.output = outputPath
        self.rootDir = rootDir

    def writeTile(self, tile, image):
        path = '%s/%s/%s' % (self.rootDir, tile.z, tile.x)
        dirPath = '%s/%s' % (self.output.absoluteFilePath(), path)
        QDir().mkpath(dirPath)
        image.save('%s/%s.png' % (dirPath, tile.y), 'PNG')

    def finalize(self):
        pass


class ZipWriter:
    def __init__(self, outputPath, rootDir):
        self.output = outputPath
        self.rootDir = rootDir

        self.zipFile = zipfile.ZipFile(
            unicode(self.output.absoluteFilePath()), 'w')
        self.tempFile = QTemporaryFile()
        self.tempFile.setAutoRemove(False)
        self.tempFile.open(QIODevice.WriteOnly)
        self.tempFileName = self.tempFile.fileName()
        self.tempFile.close()

    def writeTile(self, tile, image):
        path = '%s/%s/%s' % (self.rootDir, tile.z, tile.x)

        image.save(self.tempFileName, 'PNG')
        tilePath = '%s/%s.png' % (path, tile.y)
        self.zipFile.write(
            unicode(self.tempFileName), unicode(tilePath).encode('utf8'))

    def finalize(self):
        self.tempFile.close()
        self.tempFile.remove()
        self.zipFile.close()


class MBTilesWriter:
    def __init__(self, outputPath, rootDir):
        self.output = outputPath
        self.rootDir = rootDir

        self.connection = mbtiles_connect(
            unicode(self.output.absoluteFilePath()))
        self.cursor = self.connection.cursor()
        optimize_connection(self.cursor)
        mbtiles_setup(self.cursor)

    def writeTile(self, tile, image):
        data = QByteArray()
        buff = QBuffer(data)
        image.save(buff, 'PNG')

        self.cursor.execute('''INSERT INTO tiles(zoom_level, tile_column,
            tile_row, tile_data) VALUES (?, ?, ?, ?);''',
            (tile.z, tile.x, tile.y, sqlite3.Binary(buff.data())))
        buff.close()

    def finalize(self):
        optimize_database(self.connection)
        self.connection.commit()
        self.connection.close()
        self.cursor = None
