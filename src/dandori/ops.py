import os
import subprocess as sp

import ruamel.yaml
from box import Box

import dandori.env
import dandori.exception
import dandori.log
import dandori.process

L = dandori.log.get_logger(__name__)


class Operation:
    def fail(self, message):
        """Fail action with some message"""
        raise dandori.exception.Failure(message)

    def cancel(self, message):
        """Cancel action with some message"""
        raise dandori.exception.Cancel(message)

    def run(self, args, secret=False, **kwargs):
        """subprocess wrapper"""
        if "encoding" not in kwargs:
            kwargs["encoding"] = "utf-8"
        kwargs.setdefault("check", True)
        # Always inherit env vars
        env = os.environ.copy()
        env.update(kwargs.get("env", {}))
        kwargs["env"] = env
        if not secret and dandori.log.get_levelname() == "DEBUG":
            kwargs["echo"] = True
        try:
            if not secret:
                L.verbose3("Execute: %s", args)
            return dandori.process.run(args, **kwargs)
        except sp.CalledProcessError as e:
            L.error("Finished with code=%d: %s", e.returncode, args)
            raise

    def run_venv(self, *args, python_path="python", name="venv", **kwargs):
        """Run command with virtualenv"""
        env = self._prepare_venv(python_path, name)
        kwargs.setdefault("env", {}).update(env)
        return self.run(*args, **kwargs)

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

    def _prepare_venv(self, python_path, name):
        venv_dir = dandori.env.tempdir() / name
        if not venv_dir.exists():
            self.run([python_path, "-m", "venv", "--clear", "--symlinks", str(venv_dir)])
        if not venv_dir.exists():
            raise dandori.exception.Failure(f"Virtualenv directory does not exist: {venv_dir}")
        return {
            "VIRTUAL_ENV": str(venv_dir),
            "PATH": f"{venv_dir}/bin:{os.environ['PATH']}",
        }
