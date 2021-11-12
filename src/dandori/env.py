from __future__ import annotations

import os
import pathlib
import tempfile

TEMP_DIR = None


def is_local():
    """determin executed environment. local or in actions"""
    return os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("CI") != "true"


def tempdir() -> pathlib.Path:
    """create temporary directory and cache. need to cleanup somewhere"""
    global TEMP_DIR  # pylint: disable=global-statement
    if TEMP_DIR is None or not os.path.exists(TEMP_DIR.name):
        basedir = os.environ.get("DANDORI_TEMP_DIR")
        TEMP_DIR = tempfile.TemporaryDirectory(prefix="dandori_", dir=basedir)
    return pathlib.Path(TEMP_DIR.name).resolve()


def cachedir() -> pathlib.Path:
    """globel cache dir"""
    return pathlib.Path(os.environ.get("XDG_CACHE_DIR", "~/.cache")).joinpath("dandori").expanduser().resolve()
