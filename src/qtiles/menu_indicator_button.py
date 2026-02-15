from typing import Optional

from qgis.PyQt.QtCore import QRect, QSize, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QSizePolicy,
    QStyle,
    QStyleOptionToolButton,
    QStylePainter,
    QToolButton,
    QWidget,
)


class MenuIndicatorButton(QToolButton):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the MenuIndicatorButton.

        :param parent: Parent widget
        """
        super().__init__(parent)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
        )

        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    def _indicator_width(self) -> int:
        """
        Calculate the width of the dropdown indicator.

        :return: Indicator width in pixels
        """
        option = QStyleOptionToolButton()
        option.initFrom(self)
        return self.style().pixelMetric(
            QStyle.PixelMetric.PM_MenuButtonIndicator, option, self
        )

    def sizeHint(self) -> QSize:
        """
        Get the recommended size for the button.

        :return: Recommended size
        """
        width = self._indicator_width()

        option = QStyleOptionToolButton()
        option.initFrom(self)
        option.features = (
            QStyleOptionToolButton.ToolButtonFeature.MenuButtonPopup
        )
        option.subControls = QStyle.SubControl.SC_ToolButtonMenu

        base = self.style().sizeFromContents(
            QStyle.ContentsType.CT_ToolButton,
            option,
            QSize(width, width),
            self,
        )

        base.setWidth(width)
        return base

    def minimumSizeHint(self) -> QSize:
        """
        Get the minimum size hint.

        :return: Minimum recommended size
        """
        return self.sizeHint()

    def paintEvent(self, event) -> None:
        """
        Paint the button with dropdown indicator.

        :param event: Paint event
        """
        painter = QStylePainter(self)

        option = QStyleOptionToolButton()
        option.initFrom(self)

        frame_width = self.style().pixelMetric(
            QStyle.PixelMetric.PM_DefaultFrameWidth, option, self
        )
        pixel_ratio = self.devicePixelRatioF()

        top_shift = frame_width
        bottom_shift = frame_width

        if pixel_ratio != 1:
            pass  # TODO: Add handling of uncommon DPI

        adjusted_rect = self.rect().adjusted(0, top_shift, 0, -bottom_shift)
        option.rect = adjusted_rect

        option.features = (
            QStyleOptionToolButton.ToolButtonFeature.MenuButtonPopup
        )
        option.subControls = QStyle.SubControl.SC_ToolButtonMenu
        option.activeSubControls = QStyle.SubControl.SC_None
        option.text = ""
        option.icon = QIcon()
        option.arrowType = Qt.ArrowType.DownArrow
        option.toolButtonStyle = Qt.ToolButtonStyle.ToolButtonIconOnly

        option.state |= QStyle.StateFlag.State_Raised
        if self.underMouse():
            option.state |= QStyle.StateFlag.State_MouseOver
        if self.isDown():
            option.state |= QStyle.StateFlag.State_Sunken

        painter.drawPrimitive(
            QStyle.PrimitiveElement.PE_IndicatorButtonDropDown, option
        )
        painter.drawPrimitive(
            QStyle.PrimitiveElement.PE_IndicatorArrowDown, option
        )

    def gap(self) -> int:
        """
        Calculate the gap between button and menu indicator.

        :return: Gap in pixels (positive = gap, 0 = flush, negative = overlap)
        """
        option = QStyleOptionToolButton()
        option.initFrom(self)
        option.features |= (
            QStyleOptionToolButton.ToolButtonFeature.MenuButtonPopup
        )
        option.subControls = (
            QStyle.SubControl.SC_ToolButton
            | QStyle.SubControl.SC_ToolButtonMenu
        )

        size = self.sizeHint()
        option.rect = QRect(0, 0, size.width(), size.height())

        style = self.style()
        main_rect = style.subControlRect(
            QStyle.ComplexControl.CC_ToolButton,
            option,
            QStyle.SubControl.SC_ToolButton,
            self,
        )
        menu_rect = style.subControlRect(
            QStyle.ComplexControl.CC_ToolButton,
            option,
            QStyle.SubControl.SC_ToolButtonMenu,
            self,
        )

        return menu_rect.left() - main_rect.right() - 1
