import dataclasses
import importlib
import pathlib
import shutil

import yaml

from dandori import env


@dataclasses.dataclass
class PackagePath:
    kind: str  # local, git, remote
    path: str
    subdir: str = ""  # git only
    revision: str = ""  # git only


class Package:
    """Load user module/package/script and run specific function"""

    def __init__(self, name: str, path: PackagePath):
        """user defined script package/module"""
        self._name = name
        self._path = path
        self._mod = None

    @property
    def name(self):
        """package name in yaml configuration"""
        return self._name

    def get_function(self, func_name: str):
        """Run function corresponding to the action name

        Args:
            func_name (str): an function name of this package
        """
        self._mod = self._load_module()
        return getattr(self._mod, func_name, None)

    def _load_module(self):
        self._deploy_package()
        return importlib.import_module(f"dandori.packages.{self._name}")

    def _deploy_package(self):
        rootdir = pathlib.Path(env.tempdir().name).joinpath("packages")
        rootdir.mkdir(exist_ok=True)
        rootdir.joinpath("__init__.py").touch()
        if self._path.kind == "local":
            path = pathlib.Path(self._path.path)
            if not path.exists():
                raise ValueError(f"{path} does not exist")
            if path.is_file():
                shutil.copy(path, rootdir.joinpath(self._name + ".py"))
            elif path.is_dir():
                pkgdir = rootdir.joinpath(self._name)
                if pkgdir.exists():
                    shutil.rmtree(pkgdir)
                shutil.copytree(path, pkgdir)
        else:
            raise NotImplementedError()


@dataclasses.dataclass
class Condition:
    types: list[str]
    branches: list[str]
    branches_ignore: list[str]
    tags: list[str]
    tags_ignore: list[str]
    paths: list[str]
    paths_ignore: list[str]


@dataclasses.dataclass
class Config:
    packages: list[Package]
    conditions: dict[str, Condition]


class ConfigLoader:
    """Load local/remote configurations and script/package"""

    def load(self, path: pathlib.Path):
        """load dandori.yaml configuration file"""
        with path.open() as f:
            yaml_conf = yaml.safe_load(f)
        return Config(
            packages=self._parse_packages(yaml_conf, path.parent), conditions=self._parse_conditions(yaml_conf)
        )

    def _parse_conditions(self, conf: dict) -> dict[str, "Condition"]:
        d = {}
        for key, value in conf.get("conditions", {}):
            d[key] = Condition(
                types=value.get("types", []),
                branches=value.get("branches", []),
                branches_ignore=value.get("branches_ignore", []),
                tags=value.get("tags", []),
                tags_ignore=value.get("tags_ignore", []),
                paths=value.get("paths", []),
                paths_ignore=value.get("paths_ignore", []),
            )
        return d

    def _parse_packages(self, conf: dict, basedir: pathlib.Path):
        packages = []
        for i, pkg in enumerate(conf.get("packages", [])):
            if isinstance(pkg, str):
                name = f"package-{i}"
                path = pkg if pathlib.Path(pkg).is_absolute() else str(basedir.joinpath(pkg))
                package_path = PackagePath(kind="local", path=path)
            elif isinstance(pkg, dict):
                name = pkg.get("name", f"package-{i}")
                if "git" in pkg:
                    package_path = PackagePath(
                        kind="git",
                        path=pkg["git"]["path"],
                        revision=pkg["git"]["revision"],
                        subdir=pkg["git"]["subdir"],
                    )
                elif "path" in pkg:
                    path = (
                        pkg["path"] if pathlib.Path(pkg["path"]).is_absolute() else str(basedir.joinpath(pkg["path"]))
                    )
                    package_path = PackagePath(kind="local", path=path)
                else:
                    raise ValueError(f"Unknown action: {pkg}")
            else:
                raise ValueError(f"Unknown action: {pkg}")
            packages.append(Package(name, package_path))
        return packages
