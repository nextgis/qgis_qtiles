from typing import Optional

from qgis.core import QgsCoordinateReferenceSystem
from qgis.gui import QgsExtentWidget
from qgis.PyQt.QtWidgets import QAction, QToolButton, QWidget
from qgis.utils import iface


class QTilesExtentWidget(QgsExtentWidget):
    """
    Condensed extent selection widget used in QTiles plugin.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Create a new extent widget with condensed UI style.

        :param parent: Optional parent widget.
        """
        super().__init__(parent)

        self._map_canvas = iface.mapCanvas()

        self.setMapCanvas(self._map_canvas)
        self.setOutputCrs(QgsCoordinateReferenceSystem.fromEpsgId(4326))
        self.clear()

        self.__extend_toolbutton_menu()

    def __extend_toolbutton_menu(self) -> None:
        """
        Extends the internal tool button menu with custom actions.
        """
        buttons = self.findChildren(QToolButton)
        if not buttons:
            return

        menu = buttons[0].menu()
        if menu is None:
            return

        menu.addSeparator()

        action_full_extent = QAction(self.tr("Full project extent"), self)
        action_full_extent.triggered.connect(self._set_full_project_extent)

        menu.addAction(action_full_extent)

    def _set_full_project_extent(self) -> None:
        """
        Sets the extent to the full extent of the current QGIS project.
        """
        extent = self._map_canvas.fullExtent()
        crs = self._map_canvas.mapSettings().destinationCrs()

        self.setOutputExtentFromUser(extent, crs)
