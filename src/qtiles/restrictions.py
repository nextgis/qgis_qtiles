from abc import ABC, abstractmethod
from typing import List, Tuple

from qgis.core import QgsMapLayer
from qgis.PyQt.QtCore import QCoreApplication, QUrl


class LayerRestriction(ABC):
    @abstractmethod
    def check(self, layers, tiles_count) -> Tuple[bool, str, List]:
        pass


class OpenStreetMapRestriction(LayerRestriction):
    MAXIMUM_OPENSTREETMAP_TILES_FETCH = 5000

    def is_openstreetmap_layer(self, layer: QgsMapLayer) -> bool:
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
                        "The following OpenStreetMap layers will be skipped because the operation "
                        "would lead to bulk downloading, which is prohibited by the "
                        "<a href='https://operations.osmfoundation.org/policies/tiles/'>OpenStreetMap Foundation Tile Usage Policy</a>:",
                    )
                }</p>
                <p>{layers_list_html}</p>
                """
                return True, message, layers

        return False, message, layers
