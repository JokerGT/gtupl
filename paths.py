"""Where GTUpl keeps its own files (preferences, history, logs).

Windows keeps the existing behaviour: next to the executable when frozen,
next to the sources when run from source. A macOS app bundle must not be
written into (it lives in /Applications and a modified bundle breaks the
Gatekeeper check), so macOS uses the per-user Application Support folder;
Linux follows the XDG data directory.
"""
import os
import sys

APP_NAME = "GTUpl"


def source_dir():
    """Folder of the running program (bundle or sources)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def data_dir():
    """Writable per-user folder for preferences, history and logs."""
    if sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support", APP_NAME)
    elif sys.platform.startswith("linux"):
        xdg = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        base = os.path.join(xdg, APP_NAME.lower())
    else:
        base = source_dir()
    os.makedirs(base, exist_ok=True)
    return base


def is_macos():
    return sys.platform == "darwin"
