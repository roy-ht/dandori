from __future__ import annotations

import dataclasses
import importlib
import os
import pathlib
import pprint
import re
import shutil
import typing as T

from box import Box

import dandori.log
from dandori import env, exception, ops

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
    def __init__(self, name: str):
        """Handler loader for local path"""
        self._module_name = name

    @property
    def module_name(self):
        """module name. dynamically loaded full package name is dandori.handlers.{module_name}"""
        return self._module_name

    def load_module(self):
        """load module"""
        return importlib.import_module(f"dandori.handlers.{self._module_name}")

    def deploy_package(self):
        """Retrieve package files and place it to temporal package directory"""
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
            shutil.copy(path, rootdir.joinpath(self.module_name + ".py"))
        else:
            pkgdir = rootdir.joinpath(self.module_name)
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
        key_file: T.Optional[str] = None,
        username: str = "git",
        password_env: T.Optional[str] = None,
    ):
        """Handler loader for git url"""
        super().__init__(name)
        self._url = url
        self._revision = revision
        self._path = path or ""
        self._key_file = key_file
        self._username = username
        self._password_env = password_env

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
        envvar = {}
        if self._key_file:
            if self._url.startswith("http"):
                raise ValueError("If you use ssh key, url must be a ssh style.")
            L.verbose3("Using key file: %s", self._key_file)
            envvar["GIT_SSH_COMMAND"] = f"ssh -i {self._key_file} -F /dev/null"
            url = self._url
        elif self._password_env:
            if not os.environ.get(self._password_env):
                raise ValueError(f"Environment variable {self._password_env} not found.")
            if not self._url.startswith("http"):
                raise ValueError("If you use password_env, url must be a https style")
            L.verbose3("Git auth with token")
            helper_path = pathlib.Path(env.tempdir().name).joinpath("askpass_helper")
            with helper_path.open("w", encoding="utf-8") as f:
                f.write(f"""#!/bin/sh\necho password=${self._password_env}""")
            envvar["GIT_ASKPASS"] = str(helper_path)
            url_parts = self._url.split("://", 1)
            url = f"{url_parts[0]}://{self._username}@{url_parts[1]}"
        op = ops.Operation()
        dstdir = pathlib.Path(env.tempdir().name).joinpath("remote_git", self.module_name)
        L.verbose2("git clone: url=%s, revision=%s, path=%s", url, self._revision, self._path)
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
    local: bool = False  # Run in local mode or not
    cwd: pathlib.Path = pathlib.Path(".").absolute()  # current directory at instance generation point
    options: Box = dataclasses.field(default_factory=Box)


class ConfigLoader:
    """Load local/remote configurations and script/package"""

    def load(self, config_file):
        """load configuration file"""
        if config_file:
            path = pathlib.Path(config_file)  # ensure Path
            if not path.exists():
                raise exception.DandoriError(f"File not found: {path}")
        else:
            path = pathlib.Path("dandori.yaml")
            if not path.exists():
                path = pathlib.Path("pyproject.toml")
                if not path.exists():
                    raise exception.DandoriError(
                        "config file not found. You need to create dandori.yaml or write configs in pyproject.toml"
                    )

        if path.suffix in (".yaml", ".yml"):
            conf = Box.from_yaml(filename=str(path))
        elif path.suffix == ".toml":
            conf = Box.from_toml(filename=str(path))
            if "dandori" in conf.get("tool", {}):  # pyproject.toml support
                conf = conf["tool"]
            if "dandori" not in conf:
                raise ValueError(f"{path}: dandori section not found in your config file")
            conf = conf["dandori"]
        else:
            raise exception.DandoriError(f"Unsupported configuration format: {path}")
        L.debug("Config: %s", pprint.pformat(conf))
        return Config(handlers=self._parse_handlers(conf, path.parent), options=self._parse_options(conf))

    def _parse_handlers(self, conf: dict, basedir: pathlib.Path):
        """load handler config

        spec of handlers:
        - string: local directory
        - {'name', 'path'}: local directory with package name
        - {'name', 'git': {'revision', 'key_file', 'token_env'}}: git repo
          - key_file: path to ssh key
          - token_env: environment variable name of GITHUB_TOKEN
        """
        rootdir = pathlib.Path(env.tempdir().name).joinpath("handlers")
        rootdir.mkdir(exist_ok=True)
        rootdir.joinpath("__init__.py").touch()
        handlers = []
        for i, d in enumerate(conf.get("handlers", [])):
            if isinstance(d, str):
                name = f"package_{i}"
                path = pathlib.Path(d)
                if not path.is_absolute():
                    path = basedir.joinpath(path)
                loader = LocalHandlerLoader(name=name, path=path)
            elif isinstance(d, dict):
                name = d.get("name", f"package_{i}")
                if "git" in d:
                    gd = d["git"]
                    loader = GitHandlerLoader(name=name, **gd)
                elif "path" in d:
                    path = pathlib.Path(d["path"])
                    if not path.is_absolute():
                        path = basedir.joinpath(path)
                    loader = LocalHandlerLoader(name=name, path=path)
                else:
                    raise ValueError("Need at least one key: [path, git]")
            else:
                raise ValueError(f"handlers.{i} must be dict or str")
            handlers.append(Handler(loader))
            L.verbose3("Add handlers: %s", name)
        return handlers

    def _parse_options(self, conf: Box):
        return conf.get("options", Box())
