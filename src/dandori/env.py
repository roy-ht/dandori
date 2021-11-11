from __future__ import annotations

import os
import pathlib
import tempfile

TEMP_DIR = None


def setup():
    """Setup environment variables and some util"""
    if "DANDORI_GITHUB_TOKEN" in os.environ:
        os.environ["GITHUB_TOKEN"] = os.environ["DANDORI_GITHUB_TOKEN"]
    if not is_local():
        bindir = tempdir().joinpath("bin")
        bindir.mkdir()
        if os.environ.get("PATH"):
            os.environ["PATH"] = f"{bindir}:{os.environ['PATH']}"
        _create_git_cred_helper(bindir)


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


def _create_git_cred_helper(bindir: pathlib.Path):
    path = bindir.joinpath("git-credential-dandori")
    with path.open("w") as fo:
        fo.write(
            r"""#!/bin/sh
echo protocol=https
echo host=github.com
echo username=$1
eval "echo \"password=\${$2}\""
"""
        )
    path.chmod(0o755)
