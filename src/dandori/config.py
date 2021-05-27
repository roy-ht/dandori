from __future__ import annotations

import dataclasses
import importlib
import pathlib
import pprint
import re
import shutil
import typing as T

import tomlkit

import dandori.log
from dandori import env
from dandori.ops import Operation

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
    def __init__(self, module_name: str):
        """Base class of handler loader"""
        self._module_name = module_name

    @property
    def module_name(self):
        """module name. dynamically loaded full package name is dandori.handlers.{module_name}"""
        return self._module_name

    def load_module(self):
        """load module"""
        return importlib.import_module(f"dandori.handlers.{self._module_name}")

    def deploy_package(self):
        """retrieve package files and place it to temporal package directory"""
        raise NotImplementedError()


class LocalHandlerLoader(HandlerLoader):
    def __init__(self, name: str, path: pathlib.Path):
        """Handler loader for local path"""
        super().__init__(name)
        self._path = path

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


class GitHandlerLoader(HandlerLoader):
    def __init__(
        self,
        name: str,
        url: str,
        revision: T.Optional[str] = None,
        path: T.Optional[str] = None,
        key: T.Optional[str] = None,
    ):
        """Handler loader for git url"""
        super().__init__(name)
        self._url = url
        self._revision = revision
        self._path = path or ""
        self._key = key

    def deploy_package(self):
        """Retrieve package files and place it to temporal package directory"""
        cloned_path = self._clone()
        rootdir = pathlib.Path(env.tempdir().name).joinpath("handlers")
        if not cloned_path.exists():
            raise ValueError(f"{cloned_path} does not exist")
        if cloned_path.is_file():
            shutil.copy(cloned_path, rootdir.joinpath(self._module_name + ".py"))
        else:
            pkgdir = rootdir.joinpath(self._module_name)
            if pkgdir.exists():
                shutil.rmtree(pkgdir)
            shutil.copytree(cloned_path, pkgdir)

    def _clone(self):
        """Clone this repo into dst"""
        op = Operation()
        dstdir = pathlib.Path(env.tempdir().name).joinpath("remote_git", self.module_name)
        L.verbose2("git clone: url=%s, revision=%s, path=%s", self._url, self._revision, self._path)
        envvar = {}
        if self._key:
            L.verbose3("Using key file: %s", self._key)
            envvar["GIT_SSH_COMMAND"] = f"ssh -i {self._key} -F /dev/null"
        dstdir.mkdir(parents=True, exist_ok=True)
        cwd = str(dstdir)
        op.run(["git", "init"], cwd=cwd, env=envvar)
        op.run(["git", "remote", "add", "origin", self._url], cwd=cwd, env=envvar)
        rev = self._revision
        if not rev:
            r = op.run(["git", "remote", "show", "origin"], cwd=cwd, env=envvar)
            mo = re.search(r"^\s+HEAD branch: (.+)$", r.stdout.decode("utf-8"), re.M)
            if mo:
                rev = mo[1].strip()
            else:
                rev = "main"
            L.verbose2("Revision automatically set: %s", rev)
        op.run(["git", "fetch", "--depth", "1", "origin", rev], cwd=cwd, env=envvar)
        op.run(["git", "-c", "advice.detachedHead=false", "checkout", "FETCH_HEAD"], cwd=cwd, env=envvar)
        shutil.rmtree(dstdir.joinpath(".git"))
        if self._path:
            return dstdir.joinpath(self._path)
        else:
            return dstdir


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

    def get_function(self, event_name: str):
        """Run function corresponding to the action name

        Args:
            event_name (str): an event name to handle
        """
        func_name = f"handle_{event_name}"
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
        return Config(handlers=self._parse_handlers(conf, path.parent))

    def _parse_handlers(self, conf: dict, basedir: pathlib.Path):
        rootdir = pathlib.Path(env.tempdir().name).joinpath("handlers")
        rootdir.mkdir(exist_ok=True)
        rootdir.joinpath("__init__.py").touch()
        handlers = []
        for i, d in enumerate(conf.get("handlers", [])):
            if not isinstance(d, dict):
                raise ValueError(f"handlers.{i} must be dict")
            name = d.get("name", f"package_{i}")
            if "git" in d:
                loader: HandlerLoader = GitHandlerLoader(
                    name=name, url=d["git"], revision=d.get("revision"), path=d.get("path"), key=d.get("key")
                )
            elif "local" in d:
                path = d["local"]
                if not pathlib.Path(path).is_absolute():
                    path = str(basedir.joinpath(path))
                loader = LocalHandlerLoader(name=name, path=path)
            else:
                raise ValueError(f"Unknown handler type: {d}")
            handlers.append(Handler(loader))
            L.verbose3("Add handlers: %s", name)
        return handlers
