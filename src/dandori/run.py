import contextlib
import importlib.machinery
import pathlib
import sys
import typing as T

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

    def __init__(self, path: pathlib.Path, options: dict):
        """Running some user defined function"""
        self._cfg_path = path
        self._options = options

    def execute(self, run_command=None):
        """Setup config, execute function"""
        ctx = self._create_context()
        with self._setup():
            self._execute(ctx, run_command)

    def _execute(self, ctx: Context, run_command: T.Optional[str]):
        for handler in ctx.cfg.handlers:
            condition = handler.get_condition(ctx.gh.event_name)
            if not condition.check(ctx):
                L.verbose1("%s: skip handler for %s because of condition failed", handler.name, ctx.gh.event_name)
                continue
            if run_command:
                func_name = f"cmd_{run_command}"
            else:
                func_name = f"handle_{ctx.gh.event_name}"
            func = handler.get_function(func_name)
            if not func:
                L.verbose1("%s: function %s not found", handler.name, func_name)
                continue
            L.verbose1("%s: execute %s", handler.name, func_name)
            try:
                with ctx.gh.check(f"dandori::{ctx.gh.event_name}"):
                    r = func(ctx)
            except Exception as e:
                print(f"::error::{e}")
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
        self._update_options(self._options, config.options)
        L.verbose3("Options: %s", config.options)
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

    def _update_options(self, d1, d2):
        """merge contents of d1 into d2"""
        for key, value in d1.items():
            if isinstance(value, dict):
                d2.setdefault(key, {})
                self._update_options(value, d2[key])
            else:
                d2[key] = value
