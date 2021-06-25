import os
import pathlib
import subprocess as sp

import ruamel.yaml
from box import Box

import dandori.env
import dandori.exception
import dandori.log

L = dandori.log.get_logger(__name__)


class Operation:
    def fail(self, message):
        """Fail action with some message"""
        raise dandori.exception.Failure(message)

    def cancel(self, message):
        """Cancel action with some message"""
        raise dandori.exception.Cancel(message)

    def run(self, *args, **kwargs):
        """subprocess wrapper"""
        if "stdout" not in kwargs and "stderr" not in kwargs:
            kwargs.setdefault("capture_output", True)
        kwargs.setdefault("check", True)
        try:
            return sp.run(*args, **kwargs)  # pylint: disable=subprocess-run-check
        except sp.CalledProcessError as e:
            L.error(
                "Finished with code=%d.\n---- stdout ----\n%s\n---- stderr ----\n%s",
                e.returncode,
                e.output or "",
                e.stderr or "",
            )
            raise

    def run_venv(self, *args, python_path="python", **kwargs):
        """Run command with virtualenv"""
        env = self._prepare_venv(python_path)
        kwargs.setdefault("env", {}).update(env)
        self.run(*args, **kwargs)

    def parse_toml(self, path: str, encoding="utf-8"):
        """Parse toml file"""
        return Box.from_toml(filename=path, encoding=encoding)

    def parse_yaml(self, path: str, encoding="utf-8"):
        """Parse toml file"""
        return Box.from_yaml(filename=path, encoding=encoding)

    def dump_toml(self, obj, path: str, encoding="utf-8"):
        """Dump toml file"""
        Box(obj).to_toml(filename=path, encoding=encoding)

    def dump_yaml(self, obj, path: str, encoding="utf-8"):
        """Dump toml file"""
        if isinstance(obj, (dict, Box)):
            Box(obj).to_yaml(filename=path, encoding=encoding)
        else:
            yaml = ruamel.yaml.YAML()
            with open(path, "w", encoding=encoding) as fo:
                yaml.dump(obj, fo)

    def _prepare_venv(self, python_path):
        venv_dir = pathlib.Path(dandori.env.tempdir().name) / "venv"
        if not venv_dir.exists():
            self.run([python_path, "-m", "venv", "--clear", "--symlinks", str(venv_dir)])
            self.run_venv(["pip", "install", "-U", "pip"])
        if not venv_dir.exists():
            raise dandori.exception.Failure(f"Virtualenv directory does not exist: {venv_dir}")
        return {
            "VIRTUAL_ENV": str(venv_dir),
            "PATH": f"{venv_dir}/bin:{os.environ['PATH']}",
        }
