from __future__ import annotations

import dataclasses
import importlib
import pathlib
import pprint
import re
import shutil

from box import Box

import dandori.log
from dandori import env, exception, git, ops

L = dandori.log.get_logger(__name__)


class HandlerLoader:
    def __init__(self, name: str):
        """Handler loader for local path"""
        self._module_name = name
        self._deployed = False

    @property
    def module_name(self):
        """module name. dynamically loaded full package name is dandori.handlers.{module_name}"""
        return self._module_name

    def load_module(self):
        """load module"""
        if not self._deployed:
            self._deployed = True
            self.deploy_package()
        return importlib.import_module(f"dandori.handlers.{self._module_name}")

    def copy_package(self, path):
        """Place it to temporal package directory"""
        rootdir = env.tempdir().joinpath("handlers")
        path = pathlib.Path(path)
        if not path.exists():
            raise ValueError(f"{path} does not exist")
        if path.is_file():
            pkgfile = rootdir.joinpath(self.module_name + ".py")
            shutil.copy(path, pkgfile)
            L.debug("copy file from %s into %s", path, pkgfile)
        else:
            pkgdir = rootdir.joinpath(self.module_name)
            if pkgdir.exists():
                shutil.rmtree(pkgdir)
            shutil.copytree(path, pkgdir)
            L.debug("copy tree from %s into %s", path, pkgdir)
        if dandori.log.get_levelname() == "DEBUG":
            ops.Operation().run(["ls", "-alh", str(rootdir)])

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
        super().copy_package(self._path)


class GitHandlerLoader(HandlerLoader):
    def __init__(
        self,
        *,
        name: str,
        org: str,
        repo: str,
        protocol: str = "ssh",
        revision: str = "",
        path: str = "",
    ):
        """Handler loader for git url"""
        super().__init__(name)
        self._org = org
        self._repo = repo
        self._protocol = protocol
        self._revision = revision
        self._path = path

    @property
    def url(self):
        """clone url"""
        if self._protocol == "ssh":
            return f"git@github.com:{self._org}/{self._repo}.git"
        else:
            return f"https://github.com/{self._org}/{self._repo}.git"

    def deploy_package(self):
        """Retrieve package files and place it to temporal package directory"""
        cloned_path = self._clone()
        super().copy_package(cloned_path)

    def _clone(self) -> pathlib.Path:
        """Clone this repo into dst"""
        op = ops.Operation()
        root = env.cachedir().joinpath(self._org, self._repo, self._revision)
        if not root.is_dir():
            root.mkdir(parents=True, exist_ok=True)
            cwd = str(root)
            L.verbose2("git clone: url=%s, revision=%s, path=%s", self.url, self._revision, self._path)
            op.run(["git", "init"], cwd=cwd, echo=False)
            op.run(["git", "remote", "add", "origin", self.url], cwd=cwd, echo=False)
            rev = self._revision
            if not rev:
                r = op.run(["git", "remote", "show", "origin"], cwd=cwd, echo=False)
                mo = re.search(r"^\s+HEAD branch: (.+)$", r.stdout.decode("utf-8"), re.M)
                if mo:
                    rev = mo[1].strip()
                else:
                    rev = "main"
                L.verbose2("Revision automatically set: %s", rev)
            op.run(["git", "fetch", "--depth", "1", "origin", rev], cwd=cwd, echo=False)
            op.run(["git", "-c", "advice.detachedHead=false", "checkout", "FETCH_HEAD"], cwd=cwd, echo=False)
        if self._path:
            return root.joinpath(self._path)
        else:
            return root


class Handler:
    """Load user module/package/script and run specific function"""

    def __init__(self, loader: HandlerLoader):
        """user defined script package/module"""
        self._loader = loader
        self._mod = None

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
        self._setup_git(conf)
        return Config(
            local=env.is_local(), handlers=self._parse_handlers(conf, path.parent), options=self._parse_options(conf)
        )

    def _parse_handlers(self, conf: dict, basedir: pathlib.Path):
        """load handler config

        spec of handlers:
        - string: local directory
        - {'name', 'path'}: local directory with package name
        - {'name', 'git': <git config>}: git repo
        """
        rootdir = env.tempdir().joinpath("handlers")
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

    def _setup_git(self, conf: Box):
        git_option = conf.get("git")
        if git_option:
            git.setup(git_option)
