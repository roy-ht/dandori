import subprocess as sp

import dandori.log

L = dandori.log.get_logger(__name__)


class Operation:
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
