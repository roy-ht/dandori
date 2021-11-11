from __future__ import annotations

import contextlib
import importlib.machinery
import sys
import typing as T

from box import Box

import dandori.response

from . import env, exception, log
from .config import ConfigLoader
from .context import Context
from .gh import GitHub, GitHubMock
from .ops import Operation

L = log.get_logger(__name__)


class HandlerFinder(importlib.machinery.PathFinder):
    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        """dynamic loading of dandori.handlers"""
        L.debug("Dynamic module finder: %s, %s, %s", fullname, path, target)
        if fullname == "dandori.handlers":
            path = [str(env.tempdir())]
            spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
            return spec
        return None


class Runner:
    """Running some with user configuration"""

    def __init__(self, path, options: Box):
        """Running some user defined function"""
        self._cfg_path = path
        self._options = options

    def execute(self, invoke_function=None):
        """Setup config, execute function"""
        ctx = self._create_context()
        with self._setup():
            self._execute(ctx, invoke_function)

    def _execute(self, ctx: Context, invoke_function: T.Optional[str]):
        for handler in ctx.cfg.handlers:
            condition = handler.get_condition(ctx.gh.event_name)
            if not condition.check(ctx):
                L.verbose1("%s: skip handler for %s because of condition failed", handler.name, ctx.gh.event_name)
                continue
            if invoke_function:
                func_name = invoke_function
            else:
                func_name = f"handle_{ctx.gh.event_name}"
            func = handler.get_function(func_name)
            if not func:
                L.verbose1("%s: function %s not found", handler.name, func_name)
                continue
            L.verbose1("%s: execute %s", handler.name, func_name)
            try:
                with ctx.gh.check(f"dandori::{func_name}"):
                    r = func(ctx)
            except exception.Cancel:
                ctx.gh.cancel()
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
        config = ConfigLoader().load(self._cfg_path)
        if config.local:
            gh = GitHubMock()
        else:
            gh = GitHub()  # type: ignore
        config.options.merge_update(self._options)
        L.verbose3("Options: %s", config.options)
        ops = Operation()
        resp = dandori.response.Responses()
        return Context(gh=gh, cfg=config, ops=ops, resp=resp)

    @contextlib.contextmanager
    def _setup(self):
        sys.meta_path.append(HandlerFinder)
        try:
            yield
        finally:
            sys.meta_path.remove(HandlerFinder)
