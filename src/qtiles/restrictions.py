from abc import ABC, abstractmethod
from typing import List, Tuple

from qgis.core import QgsMapLayer
from qgis.PyQt.QtCore import QCoreApplication, QUrl


class LayerRestriction(ABC):
    """
    Abstract base class for defining restrictions on map layers.

    Subclasses must implement the `check` method to enforce specific
    restrictions on layers and tile counts.
    """

    @abstractmethod
    def check(self, layers, tiles_count) -> Tuple[bool, str, List]:
        """
        Checks whether the given layers and tile count meet the restriction.

        This method must be implemented by subclasses to define custom
        restrictions.

        :param layers: A list of map layers to check.
        :param tiles_count: The total number of tiles to be generated.
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
        if layer.providerType().lower() == "wms":
            metadata = layer.providerMetadata()
            uri = metadata.decodeUri(layer.source())
            url = QUrl(uri.get("url", ""))
            host = url.host().lower()
            if host.endswith("openstreetmap.org") or host.endswith("osm.org"):
                return True
        return False

    def check(
        self, layers: List[QgsMapLayer], tiles_count: int
    ) -> Tuple[bool, str, List[QgsMapLayer]]:
        """
        Checks if the tile count exceeds the maximum allowed for OpenStreetMap.

        If the tile count exceeds the limit, this method identifies and skips
        OpenStreetMap layers to comply with the usage policy.

        :param layers: A list of map layers to check.
        :param tiles_count: The total number of tiles to be generated.

        :returns: A tuple containing a boolean indicating whether any layers
            were skipped, a message describing the skipped layers, and the
            updated list of layers.
        """
        message = ""

        if tiles_count > self.MAXIMUM_OPENSTREETMAP_TILES_FETCH:
            osm_layers = []
            for layer in layers:
                if self.is_openstreetmap_layer(layer):
                    osm_layers.append(layer)
                    layers.remove(layer)

            if osm_layers:
                layers_list_html = "<br>".join(
                    [layer.name() for layer in osm_layers]
                )
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

                if not layers:
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
                return True, message, layers

        return False, message, layers
