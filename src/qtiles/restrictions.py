from abc import ABC, abstractmethod
from typing import List, Tuple

from qgis.core import QgsMapLayer
from qgis.PyQt.QtCore import QCoreApplication, QUrl


class LayerRestriction(ABC):
    """
    Abstract base class for defining restrictions on map layers.
    """

    @abstractmethod
    def validate_restriction(
        self, layers: List[QgsMapLayer], tiles_count: int
    ) -> Tuple[bool, str, List[QgsMapLayer]]:
        """
        Validates whether the given layers and tile count meet the restriction.

        Subclasses should implement this method to define their own logic for
        checking specific restriction (e.g., OpenStreetMap usage policy).

        :param layers: A list of map layers to check.
        :type layers: List[QgsMapLayer]

        :param tiles_count: The total number of tiles to be generated.
        :type tiles_count: int

        :returns: A tuple containing:
            - **bool** – whether the restriction is violated,
            - **str** – an HTML message describing skipped layers (if any),
            - **List[QgsMapLayer]** – list of layers to be skipped.
        :rtype: Tuple[bool, str, List[QgsMapLayer]]
        """
        pass


class OpenStreetMapRestriction(LayerRestriction):
    """
    Restriction for OpenStreetMap layers to prevent bulk downloading.

    This class enforces the OpenStreetMap Tile Usage Policy by skipping
    layers that would result in excessive tile downloads.
    """

    MAXIMUM_OPENSTREETMAP_TILES_FETCH: int = 5000

    def is_openstreetmap_layer(self, layer: QgsMapLayer) -> bool:
        """
        Determines whether a given layer is an OpenStreetMap layer.

        This method checks the provider type and URL of the layer to identify
        if it belongs to OpenStreetMap.

        :param layer: The map layer to check.
        """
        if layer.providerType().lower() != "wms":
            return False

        metadata = layer.providerMetadata()
        uri = metadata.decodeUri(layer.source())
        url = QUrl(uri.get("url", ""))
        host = url.host().lower()

        return host.endswith("openstreetmap.org") or host.endswith("osm.org")

    def validate_restriction(
        self, layers: List[QgsMapLayer], tiles_count: int
    ) -> Tuple[bool, str, List[QgsMapLayer]]:
        """
        Checks if the tile count exceeds the maximum allowed for OpenStreetMap.

        :param layers: A list of map layers to check.
        :type layers: List[QgsMapLayer]

        :param tiles_count: The total number of tiles to be generated.
        :type tiles_count: int

        :returns: A tuple containing:
            - **bool** – whether the restriction is violated,
            - **str** – an HTML message describing skipped layers (if any),
            - **List[QgsMapLayer]** – list of layers to be skipped.
        :rtype: Tuple[bool, str, List[QgsMapLayer]]
        """
        if tiles_count <= self.MAXIMUM_OPENSTREETMAP_TILES_FETCH:
            return False, "", []

        osm_layers = [
            layer for layer in layers if self.is_openstreetmap_layer(layer)
        ]

        if not osm_layers:
            return False, "", []

        layers_list_html = "<br>".join(layer.name() for layer in osm_layers)
        message = f"""
        <p>{
            QCoreApplication.translate(
                "LayerRestriction",
                "The following OpenStreetMap layers were skipped because the operation "
                "would lead to bulk downloading, which is prohibited by the "
                "<a href='https://operations.osmfoundation.org/policies/tiles/'>OpenStreetMap Foundation Tile Usage Policy</a>:",
            )
        }</p>
        <p>{layers_list_html}</p>
        """

        if len(osm_layers) == len(layers):
            message += f"""
            <p>{
                QCoreApplication.translate(
                    "LayerRestriction",
                    "There are no layers remaining for tiling. "
                    "The operation has been cancelled.",
                )
            }</p>
            """

        message += f"""
        <p>{
            QCoreApplication.translate(
                "LayerRestriction",
                "To avoid this restriction, try reducing the maximum zoom level in the settings "
                "or increasing the zoom level in the map extent before running operation.",
            )
        }</p>
        """

        return True, message, osm_layers
