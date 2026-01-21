from qtiles.writers.abstract_tiles_writer import AbstractTilesWriter
from qtiles.writers.directory_tiles_writer import DirectoryTilesWriter
from qtiles.writers.enums import TilesWriterMode
from qtiles.writers.mbtiles_writer import MBTilesWriter
from qtiles.writers.ngm_archive_tiles_writer import NGMArchiveTilesWriter
from qtiles.writers.pmtiles_writer import PMTilesWriter
from qtiles.writers.save_tiles_options import SaveTilesOptions
from qtiles.writers.zip_tiles_writer import ZipTilesWriter


class TilesWriterFactory:
    """
    Factory responsible for creating concrete tile writer instances.
    """

    @staticmethod
    def create(
        mode: TilesWriterMode, options: SaveTilesOptions
    ) -> AbstractTilesWriter:
        """
        Creates a concrete tile writer.

        :param mode: Tile writer mode.
        :type mode: TilesWriterMode
        :param options: Configuration for tile saving.
        :type options: SaveTilesOptions

        :returns: Concrete instance of a tiles writer.
        :rtype: AbstractTilesWriter
        """
        if mode is TilesWriterMode.DIR:
            return DirectoryTilesWriter(
                output_path=options.output_path,
                root_dir=options.root_dir,
            )
        if mode is TilesWriterMode.ZIP:
            return ZipTilesWriter(
                output_path=options.output_path,
                root_dir=options.root_dir,
            )
        if mode is TilesWriterMode.NGM:
            return NGMArchiveTilesWriter(
                output_path=options.output_path,
                root_dir=options.root_dir,
            )
        if mode is TilesWriterMode.MBTILES:
            return MBTilesWriter(
                output_path=options.output_path,
                root_dir=options.root_dir,
                image_format=options.image_format,
                min_zoom=options.min_zoom,
                max_zoom=options.max_zoom,
                extent=options.extent,
                compression=options.compression,
            )
        if mode is TilesWriterMode.PMTILES:
            return PMTilesWriter(
                output_path=options.output_path,
                root_dir=options.root_dir,
                image_format=options.image_format,
                min_zoom=options.min_zoom,
                max_zoom=options.max_zoom,
                extent=options.extent,
            )
