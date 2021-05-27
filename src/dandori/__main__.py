import argparse
import pathlib

import dandori.log
import dandori.run


def run(args):
    """entrypoint of run command"""
    cfg = args.config_file
    if cfg is None:
        cfg = pathlib.Path("dandori.toml")
    if not cfg.exists():
        cfg = pathlib.Path("pyproject.toml")
    runner = dandori.run.Runner(cfg)
    runner.execute()


def main():
    """entrypoint of dandori command"""
    psr = argparse.ArgumentParser()
    psr.add_argument("-v", "--verbose", default=0, action="count")
    sub_psrs = psr.add_subparsers(dest="command_name", required=True, metavar="command_name")
    psr_run = sub_psrs.add_parser("run", help="Running CI Action")
    psr_run.set_defaults(func=run)
    psr_run.add_argument("-f", "--config-file", help="toml configuration file path")
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
    args.func(args)


if __name__ == "__main__":
    main()
