from typing import Optional

from qgis.core import QgsApplication, QgsCoordinateReferenceSystem
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
        menu.setToolTipsVisible(True)

        action_visible_extent = QAction(
            QgsApplication.getThemeIcon("mActionZoomFullExtent.svg"),
            self.tr("Extent of visible layers"),
            self,
        )
        action_visible_extent.setToolTip(
            self.tr(
                "Sets the extent to include all currently visible layers "
                "in the map canvas."
            )
        )
        action_visible_extent.triggered.connect(
            self._set_visible_layers_extent
        )

        action_project_extent = QAction(
            QgsApplication.getThemeIcon("mIconQgsProjectFile.svg"),
            self.tr("Full project extent"),
            self,
        )
        action_project_extent.setToolTip(
            self.tr(
                "Sets the extent to the full extent of the QGIS project, "
                "including layers which are not currently visible."
            )
        )
        action_project_extent.triggered.connect(self._set_project_extent)

        menu.addAction(action_visible_extent)
        menu.addAction(action_project_extent)

    def _set_visible_layers_extent(self) -> None:
        """
        Sets the extent to the combined extent of all visible layers.
        """
        extent = self._map_canvas.fullExtent()
        crs = self._map_canvas.mapSettings().destinationCrs()

        self.setOutputExtentFromUser(extent, crs)

    def _set_project_extent(self) -> None:
        """
        Sets the extent to the full extent of the QGIS project,
        regardless of layer visibility.
        """
        extent = self._map_canvas.projectExtent()
        crs = self._map_canvas.mapSettings().destinationCrs()

        self.setOutputExtentFromUser(extent, crs)
