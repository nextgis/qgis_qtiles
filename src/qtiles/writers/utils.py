from pathlib import Path
from string import Template
from typing import Type

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QFile, QIODevice

from qtiles.core.exceptions import (
    TileGenerationError,
    TileGenerationWarning,
)
from qtiles.core.logging import logger


def ensure_operation_succeeded(
    is_successful: bool,
    *,
    log_message: str,
    user_message: str,
    detail: str,
    warning: bool = False,
) -> None:
    """Raise a tile generation issue when an operation reports failure."""
    if is_successful:
        return

    issue_class: Type[Exception]
    issue_class = TileGenerationWarning if warning else TileGenerationError
    raise issue_class(
        log_message=log_message,
        user_message=user_message,
        detail=detail,
    )


def copy_resource(qrc_path: str, target: Path) -> None:
    """
    Copy a file from Qt resource system (`qrc_path`) to filesystem.

    :param qrc_path: Path to the resource inside the Qt resource system.
    :param target: Destination path on the filesystem.
    :returns: None.
    """
    target.parent.mkdir(parents=True, exist_ok=True)

    file = QFile(qrc_path)
    # fmt: off
    ensure_operation_succeeded(
        file.open(QIODevice.OpenModeFlag.ReadOnly),
        log_message=f"Failed to open viewer resource: {qrc_path}",
        user_message=QgsApplication.translate(
            "utils", "Viewer files were not fully generated."
        ),
        detail=QgsApplication.translate(
            "utils",
            "Could not read the embedded viewer resource '{path}'."
        ).format(path=qrc_path),
        warning=True,
    )
    # fmt: on

    data = file.readAll()
    file.close()

    try:
        with open(str(target), "wb") as resource_file:
            resource_file.write(bytes(data))
    except IOError as error:
        raise TileGenerationWarning(
            log_message=f"Failed to write viewer resource to disk: {target}",
            user_message=QgsApplication.translate(
                "utils", "Viewer files were not fully generated."
            ),
            detail=QgsApplication.translate(
                "utils", "Could not write the viewer resource to '{path}'."
            ).format(path=target, error=str(error)),
        ) from error


def create_viewer_directory(viewer_dir: Path) -> None:
    """
    Creates a Leaflet viewer directory with all required resources.

    :param viewer_dir: Desired base path for the viewer directory.
    """
    (viewer_dir / "css/images").mkdir(parents=True, exist_ok=True)
    (viewer_dir / "js/images").mkdir(parents=True, exist_ok=True)

    resources = [
        ("css/leaflet.css", "css/leaflet.css"),
        ("css/jquery-ui.min.css", "css/jquery-ui.min.css"),
        ("css/images/layers.png", "css/images/layers.png"),
        ("js/leaflet.js", "js/leaflet.js"),
        ("js/jquery.min.js", "js/jquery.min.js"),
        ("js/jquery-ui.min.js", "js/jquery-ui.min.js"),
        (
            "js/images/ui-bg_flat_75_ffffff_40x100.png",
            "js/images/ui-bg_flat_75_ffffff_40x100.png",
        ),
    ]

    for src, dest in resources:
        try:
            copy_resource(
                f":/plugins/qtiles/resources/{src}", viewer_dir / dest
            )
        except TileGenerationWarning as warning:
            logger.exception(warning.log_message)


class MyTemplate(Template):
    """
    A subclass of Python's built-in Template class
    that uses a custom delimiter "@" for variable substitution.

    This class allows template substitution
    using the "@" symbol instead of the default "${}" delimiter.
    It is used to customize the rendering of template strings
    for generating HTML files, specifically in the context of creating
    a Leaflet viewer for the tile generation process.
    """

    delimiter = "@"

    def __init__(self, template_string: str) -> None:
        """
        Initializes the MyTemplate class with the provided template string.

        :param templateString: The template string to be processed.
                               This string can contain placeholders that will be
                               replaced with actual values during template substitution.
        """
        super().__init__(template_string)
