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


class HandlerFinder(importlib.machinery.PathFinder):
    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        """dynamic loading of dandori.handlers"""
        L.debug("Dynamic module finder: %s, %s, %s", fullname, path, target)
        if fullname == "dandori.handlers":
            path = [env.tempdir().name]
            spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
            return spec
        return None


class Runner:
    """Running some with user configuration"""

    def __init__(self, path: pathlib.Path):
        """Running some user defined function"""
        self._cfg_path = path

    def execute(self):
        """Setup config, execute function"""
        ctx = self._create_context()
        with self._setup():
            self._execute(ctx)

    def _execute(self, ctx: Context):
        for handler in ctx.cfg.handlers:
            func = handler.get_function(ctx.gh.event_name)
            if not func:
                L.verbose1("%s: function handler for %s not found", handler.name, ctx.gh.event_name)
                continue
            condition = handler.get_condition(ctx.gh.event_name)
            if not condition.check(ctx):
                L.verbose1("%s: skip handler for %s because of condition failed", handler.name, ctx.gh.event_name)
                continue
            L.verbose1("%s: execute handler for %s", handler.name, ctx.gh.event_name)
            try:
                r = func(ctx)
            except Exception as e:
                L.info("::error::%s", e)
                raise

            if isinstance(r, dict):
                ctx.resp.append_dict(handler.name, r)
            elif isinstance(r, dandori.response.Response):
                ctx.resp.append(handler.name, r)
            else:
                ctx.resp.append_dict(handler.name, {})

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
        sys.meta_path.append(HandlerFinder)
        try:
            yield
        finally:
            tempdir.cleanup()
        sys.meta_path.remove(HandlerFinder)
