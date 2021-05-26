import os
import tempfile

TEMP_DIR = None


def tempdir() -> tempfile.TemporaryDirectory:
    """create temporary directory and cache. need to cleanup somewhere"""
    global TEMP_DIR  # pylint: disable=global-statement
    if TEMP_DIR is None or not os.path.exists(TEMP_DIR.name):
        basedir = os.environ.get("DANDORI_TEMP_DIR")
        TEMP_DIR = tempfile.TemporaryDirectory(prefix="dandori_", dir=basedir)
    return TEMP_DIR
