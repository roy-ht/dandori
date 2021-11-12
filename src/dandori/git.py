import os
import pathlib
import weakref

from dandori import env, ops

SETUP_GIT = None


class SetupGit:
    def __init__(self, option):
        """Setup git configuration for whole dandori process"""
        self._ssh_to_https = option.get("ssh_to_https", True)
        self.obj = self._setup()
        self._finalizer = weakref.finalize(self, self._cleanup, self.obj)

    @classmethod
    def _cleanup(cls, obj):
        # restore original git config
        if "git_config_path" in obj:
            with obj["git_config_path"].open("wb") as fo:
                fo.write(obj["git_config_content"])

    def _setup(self):
        if "DANDORI_GITHUB_TOKEN" in os.environ:
            os.environ["GITHUB_TOKEN"] = os.environ["DANDORI_GITHUB_TOKEN"]
        robj = {}
        if not env.is_local():
            bindir = env.tempdir().joinpath("bin")
            bindir.mkdir()
            if os.environ.get("PATH"):
                os.environ["PATH"] = f"{bindir}:{os.environ['PATH']}"
            self._backup_global_git_config(robj)
            self._setup_git_cred_helper(bindir)
        return robj

    def _setup_git_cred_helper(self, bindir: pathlib.Path):
        path = bindir.joinpath("git-credential-dandori-default")
        with path.open("w") as fo:
            fo.write(
                r"""#!/bin/sh
    echo protocol=https
    echo host=github.com
    echo username=git
    echo password=$DANDORI_DEFAULT_PAT
    """
            )
        path.chmod(0o755)
        op = ops.Operation()
        op.run(["git", "config", "--global", 'url."https://github.com".insteadOf', "ssh://git@github.com"])
        op.run(["git", "config", "--global", "--add", 'url."https://github.com".insteadOf', "git://git@github.com"])
        op.run(["git", "config", "--global", "--add", 'url."https://github.com/".insteadOf', "git@github.com:"])
        op.run(
            ["git", "config", "--global", "--add", "credential.helper", "dandori-default"],
        )

    def _backup_global_git_config(self, robj):
        p = pathlib.Path("~/.gitconfig").expanduser()
        if not p.is_file():
            p = pathlib.Path("~/.config/git/config").expanduser()
        if p.is_file():
            robj["git_config_path"] = p
            with p.open("rb") as f:
                robj["git_config_content"] = f.read()


def setup(opt):
    """Setup environment variables and some util"""
    global SETUP_GIT  # pylint: disable=global-statement
    if SETUP_GIT is None:
        SETUP_GIT = SetupGit(opt)
