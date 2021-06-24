from __future__ import annotations

import dataclasses
import importlib
import pathlib
import pprint
import shutil
import typing as T

import fastcore.basics
import tomlkit

import dandori.log
from dandori import env

if T.TYPE_CHECKING:
    from dandori.context import Context


L = dandori.log.get_logger(__name__)


class Condition:
    def __init__(self, src: T.Optional[dict] = None):
        """Represents handler condition to execute function or not

        Args:
            src (T.Optional[dict], optional): configuration object. Defaults to None.
        """
        self._src = src

    def check(self, ctx: Context):  # pylint: disable=unused-argument
        """Check if execute handler or not"""
        L.warning("Condition check does not implemented yet")
        return True


class HandlerLoader:
    def __init__(self, name: str, path: pathlib.Path):
        """Handler loader for local path"""
        self._module_name = name
        self._path = path

    @property
    def module_name(self):
        """module name. dynamically loaded full package name is dandori.handlers.{module_name}"""
        return self._module_name

    def load_module(self):
        """load module"""
        return importlib.import_module(f"dandori.handlers.{self._module_name}")

    def deploy_package(self):
        """Retrieve package files and place it to temporal package directory"""
        rootdir = pathlib.Path(env.tempdir().name).joinpath("handlers")
        path = pathlib.Path(self._path)
        if not path.exists():
            raise ValueError(f"{path} does not exist")
        if path.is_file():
            shutil.copy(path, rootdir.joinpath(self._module_name + ".py"))
        else:
            pkgdir = rootdir.joinpath(self._module_name)
            if pkgdir.exists():
                shutil.rmtree(pkgdir)
            shutil.copytree(path, pkgdir)


class Handler:
    """Load user module/package/script and run specific function"""

    def __init__(self, loader: HandlerLoader):
        """user defined script package/module"""
        self._loader = loader
        self._mod = None
        self._loader.deploy_package()

    @property
    def name(self):
        """module/package name in configuration or automatically named"""
        return self._loader.module_name

    def get_function(self, func_name: str):
        """Run function corresponding to the action name

        Args:
            func_name (str): function name to get
        """
        self._load_module()
        return getattr(self._mod, func_name, None)

    def get_condition(self, event_name: str):
        """Get condition object correspond to event"""
        self._load_module()
        if not hasattr(self._mod, "conditions"):
            return Condition()
        else:
            conditions = self._mod.conditions()  # type: ignore
            return Condition(conditions[event_name])

    def _load_module(self):
        if self._mod is None:
            self._mod = self._loader.load_module()


@dataclasses.dataclass
class Config:
    handlers: list[Handler]
    cwd: pathlib.Path = pathlib.Path(".").absolute()  # current directory at instance generation point
    options: fastcore.basics.AttrDict = dataclasses.field(default_factory=fastcore.basics.AttrDict)


class ConfigLoader:
    """Load local/remote configurations and script/package"""

    def load(self, path: pathlib.Path):
        """load toml configuration file"""
        with path.open("r", encoding="utf-8") as f:
            conf = tomlkit.parse(f.read())
        if "dandori" in conf.get("tool", {}):  # pyproject.toml support
            conf = conf["tool"]
        if "dandori" not in conf:
            raise ValueError(f"{path}: dandori section not found in your config file")
        conf = conf["dandori"]
        L.debug("Config: %s", pprint.pformat(conf))
        return Config(handlers=self._parse_handlers(conf, path.parent), options=self._parse_options(conf))

    def _parse_handlers(self, conf: dict, basedir: pathlib.Path):
        rootdir = pathlib.Path(env.tempdir().name).joinpath("handlers")
        rootdir.mkdir(exist_ok=True)
        rootdir.joinpath("__init__.py").touch()
        handlers = []
        for i, d in enumerate(conf.get("handlers", [])):
            if isinstance(d, str):
                name = f"package_{i}"
                path = pathlib.Path(d)
            elif isinstance(d, dict):
                name = d.get("name", f"package_{i}")
                path = pathlib.Path(d["path"])
            else:
                raise ValueError(f"handlers.{i} must be dict or str")
            if not path.is_absolute():
                path = basedir.joinpath(path)
            loader = HandlerLoader(name=name, path=path)
            handlers.append(Handler(loader))
            L.verbose3("Add handlers: %s", name)
        return handlers

    def _parse_options(self, conf: dict):
        return fastcore.basics.AttrDict(conf.get("options", {}))
