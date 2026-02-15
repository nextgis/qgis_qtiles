from math import log2
from typing import Optional

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QHBoxLayout,
    QMenu,
    QSizePolicy,
    QSpinBox,
    QWidget,
)
from qgis.utils import iface

from qtiles.menu_indicator_button import MenuIndicatorButton


class ZoomLevelSpinBox(QWidget):
    """
    Widget for zoom level selection with a spinbox and dropdown button.
    """

    value_changed = pyqtSignal(int)

    MIN_ZOOM_LEVEL = 0
    MAX_ZOOM_LEVEL = 20
    ZOMM_LEVEL_1_SCALE = 591658688

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the ZoomLevelSpinBox widget.

        :param parent: Parent widget
        """
        super().__init__(parent)
        self.__setup_ui()
        self.__setup_menu()

    def __setup_ui(self) -> None:
        """
        Initialize the UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._zoom_level_spinbox = QSpinBox(self)
        self._zoom_level_spinbox.setMinimum(0)
        self._zoom_level_spinbox.setMaximum(20)
        self._zoom_level_spinbox.setValue(0)
        self._zoom_level_spinbox.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._zoom_level_spinbox.valueChanged.connect(self.value_changed)

        self._menu_indicator_button = MenuIndicatorButton(self)

        layout.addWidget(self._zoom_level_spinbox)

        gap = self._menu_indicator_button.gap()
        if gap >= 0:
            layout.setSpacing(gap)
        else:
            layout.setSpacing(0)

        layout.addWidget(self._menu_indicator_button)
        layout.addStretch()

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def __setup_menu(self) -> None:
        self.__zoom_level_menu = QMenu(self)

        action_set_current_zoom_level = QAction(
            QIcon(QgsApplication.getThemeIcon("mIconZoom.svg")),
            self.tr("Set current zoom level"),
            self,
        )

        action_set_current_zoom_level.triggered.connect(
            self._set_zoom_from_map_scale
        )

        self.__zoom_level_menu.addAction(action_set_current_zoom_level)

        self._menu_indicator_button.setMenu(self.__zoom_level_menu)

    @property
    def spinbox(self) -> QSpinBox:
        """
        Get direct access to internal spinbox.

        :return: Internal spinbox widget
        """
        return self._zoom_level_spinbox

    @property
    def button(self) -> "MenuIndicatorButton":
        """
        Get direct access to internal button.

        :return: Internal menu indicator button
        """
        return self._menu_indicator_button

    def value(self) -> int:
        """
        Get current zoom level value.

        :return: Current spinbox value
        """
        return self._zoom_level_spinbox.value()

    def set_value(self, value: int) -> None:
        """
        Set zoom level value.

        :param value: Zoom level to set
        """
        self._zoom_level_spinbox.setValue(value)

    def set_minimum(self, minimum: int) -> None:
        """
        Set minimum zoom level value.

        :param minimum: Minimum allowed zoom level
        """
        self._zoom_level_spinbox.setMinimum(minimum)

    def set_maximum(self, maximum: int) -> None:
        """
        Set maximum zoom level value.

        :param maximum: Maximum allowed zoom level
        """
        self._zoom_level_spinbox.setMaximum(maximum)

    def set_range(self, minimum: int, maximum: int) -> None:
        """
        Set zoom level range.

        :param minimum: Minimum allowed zoom level
        :param maximum: Maximum allowed zoom level
        """
        self._zoom_level_spinbox.setRange(minimum, maximum)

    def _set_zoom_from_map_scale(self) -> None:
        """
        Calculates and sets the zoom level based on the current QGIS map scale.

        The zoom level is computed using a base-2 logarithmic transformation
        relative to ``ZOMM_LEVEL_1_SCALE`` and then rounded to the nearest integer.

        The resulting value is clamped to the inclusive range defined by
        ``MIN_ZOOM_LEVEL`` and ``MAX_ZOOM_LEVEL``.

        If the computed zoom level falls outside the current spin box range,
        the spin box boundaries are adjusted accordingly before setting the value.

        If the current map scale is non-positive, the method exits without changes.

        :return: None
        """
        canvas = iface.mapCanvas()
        map_scale = canvas.scale()

        if map_scale <= 0:
            return

        zoom = log2(self.ZOMM_LEVEL_1_SCALE / map_scale)
        zoom_int = int(round(zoom))

        zoom_int = max(
            self.MIN_ZOOM_LEVEL,
            min(zoom_int, self.MAX_ZOOM_LEVEL),
        )

        if zoom_int < self._zoom_level_spinbox.minimum():
            self._zoom_level_spinbox.setMinimum(zoom_int)

        if zoom_int > self._zoom_level_spinbox.maximum():
            self._zoom_level_spinbox.setMaximum(zoom_int)

        self._zoom_level_spinbox.setValue(zoom_int)
