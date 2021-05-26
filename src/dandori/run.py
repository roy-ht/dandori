import contextlib
import importlib.machinery
import pathlib
import sys

import dandori.response

from . import env, log
from .config import ConfigLoader
from .context import Context
from .gh import GitHub
from .ops import Operation

L = log.get_logger(__name__)


class PackageFinder(importlib.machinery.PathFinder):
    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        """dynamic loading of dandori.packages"""
        if fullname == "dandori.packages":
            path = [env.tempdir().name]
            spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
            return spec
        return None


class Runner:
    """Running some with user configuration"""

    def __init__(self, path: str):
        """Running some user defined function"""
        self._cfg_path = pathlib.Path(path)

    def execute(self):
        """Setup config, execute function"""
        ctx = self._create_context()
        with self._setup():
            self._execute(ctx)

    def _execute(self, ctx: Context):
        for pkg in ctx.cfg.packages:
            func_name = f"handle_{ctx.gh.event_name}"
            func = pkg.get_function(func_name)
            if not func:
                L.verbose1("%s: function %s not found", pkg.name, func_name)
            else:
                r = func(ctx)
                if isinstance(r, dict):
                    ctx.resp.append_dict(pkg.name, r)
                elif isinstance(r, dandori.response.Response):
                    ctx.resp.append(pkg.name, r)
                else:
                    ctx.resp.append_dict(pkg.name, {})

    def _create_context(self) -> Context:
        # load Github Actions Events
        gh = GitHub()
        config = ConfigLoader().load(self._cfg_path)
        ops = Operation()
        resp = dandori.response.Responses()
        return Context(gh=gh, cfg=config, ops=ops, resp=resp)

    @contextlib.contextmanager
    def _setup(self):
        tempdir = env.tempdir()
        sys.meta_path.append(PackageFinder)
        try:
            yield
        finally:
            tempdir.cleanup()
        sys.meta_path.remove(PackageFinder)
