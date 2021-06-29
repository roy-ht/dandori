from __future__ import annotations

import argparse
import pathlib

import ruamel.yaml
from box import Box

import dandori.log
import dandori.run


def _parse_options(lines):
    options = Box()
    yaml = ruamel.yaml.YAML(typ="safe")
    if lines:
        for line in lines:
            kvs = line.split("=", 1)
            if len(kvs) == 1:
                kdots, value = kvs[0], "true"
            else:
                kdots, value = kvs[0], yaml.load(kvs[1])
            keys = kdots.split(".")
            tgt = options
            for k in keys[:-1]:
                tgt.setdefault(k, {})
                tgt = tgt[k]
            tgt[keys[-1]] = value
    return options


def main():
    """entrypoint of dandori command"""
    args = _parse_args()
    cpath = args.config_file
    if cpath is None:
        cpath = pathlib.Path("dandori.yaml")
    else:
        cpath = pathlib.Path(cpath)
    if not cpath.exists():
        cpath = pathlib.Path("pyproject.toml")
    options = _parse_options(args.options)
    runner = dandori.run.Runner(cpath, options=options, local_mode=args.local)
    runner.execute(args.invoke)


def _parse_args():
    psr = argparse.ArgumentParser()
    psr.add_argument("-v", "--verbose", default=0, action="count")
    psr.add_argument("-f", "--config-file", help="configuration file path (toml or yaml)")
    psr.add_argument("-i", "--invoke", help="Invoke specific function manually")
    psr.add_argument(
        "-l", "--local", action="store_true", default=False, help="You can try actions on your local machine"
    )
    psr.add_argument("-o", "--options", action="append", help="optional arguments")
    args = psr.parse_args()

    # set log level
    dandori.log.set_level(
        {
            0: dandori.log.INFO,
            1: dandori.log.VERBOSE1,
            2: dandori.log.VERBOSE2,
            3: dandori.log.VERBOSE3,
            4: dandori.log.DEBUG,
        }.get(args.verbose, dandori.log.INFO)
    )

    return args


if __name__ == "__main__":
    main()
