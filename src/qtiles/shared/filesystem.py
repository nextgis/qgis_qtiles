import subprocess
import sys
from pathlib import Path


def reveal_in_file_manager(file_path: Path) -> None:
    """Reveal the given file or directory in the system's file manager.

    :param file_path: The path to the file or directory to reveal.
    """
    path = file_path.resolve()

    if sys.platform.startswith("win"):
        _reveal_in_windows(path)
        return

    if sys.platform == "darwin":
        _reveal_in_macos(path)
        return

    _reveal_in_linux(path)


def _reveal_in_windows(path: Path) -> None:
    # Use Windows Explorer. '/select,' highlights the file in its folder.
    if path.is_dir():
        subprocess.Popen(["explorer", str(path)], close_fds=True)
        return

    subprocess.Popen(["explorer", "/select,", str(path)], close_fds=True)


def _reveal_in_macos(path: Path) -> None:
    # Use Finder. '-R' reveals the file.
    if path.is_dir():
        subprocess.Popen(["/usr/bin/open", str(path)], close_fds=True)
        return

    subprocess.Popen(["/usr/bin/open", "-R", str(path)], close_fds=True)


def _reveal_in_linux(path: Path) -> None:
    # TODO: dbus
    _open_base_directory_with_xdg(path)


def _open_base_directory_with_xdg(path: Path) -> None:
    directory = path if path.is_dir() else path.parent
    subprocess.Popen(["xdg-open", str(directory)], close_fds=True)
