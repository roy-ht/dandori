"""Modified version of https://github.com/pycontribs/subprocess-tee

Copyright (c) 2020 Sorin Sbarnea
Released under the MIT license
http://opensource.org/licenses/mit-license.php

"""
from __future__ import annotations

import asyncio
import os
import subprocess as sp
import typing as T

STREAM_LIMIT = 2 ** 23  # 8MB instead of default 64kb, override it if you need


async def _read_stream(stream, outlist, echo, encoding):
    while True:
        line = await stream.readline()
        if line:
            if encoding is not None:
                line = line.decode(encoding)
            outlist.append(line)
            if echo:
                print(line)
        else:
            break


async def _stream_subprocess(args, echo=True, **kwargs) -> sp.CompletedProcess:
    kwargs.pop("stdout", None)
    kwargs.pop("stderr", None)
    kwargs.setdefault("limit", STREAM_LIMIT)
    kwargs["stdout"] = asyncio.subprocess.PIPE
    kwargs["stderr"] = asyncio.subprocess.STDOUT
    encoding = kwargs.pop("encoding", "utf-8")
    if kwargs.get("shell", False):
        proc = await asyncio.create_subprocess_shell(args, **kwargs)
    else:
        proc = await asyncio.create_subprocess_exec(args, **kwargs)

    out: list[str] = []
    loop = asyncio.get_event_loop()
    task = loop.create_task(_read_stream(proc.stdout, out, echo, encoding))
    await asyncio.wait([task])

    output = ""
    if out:
        output = os.linesep.join(out) + os.linesep

    return sp.CompletedProcess(
        args=args,
        returncode=await proc.wait(),
        stdout=output,
        stderr="",
    )


def run(args: T.Union[str, list[str]], echo=True, **kwargs) -> sp.CompletedProcess:
    """Always capture

    echo(default: True) <- print to stdout or not
    """
    check = kwargs.pop("check", False)

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(_stream_subprocess(args, echo=echo, **kwargs))
    if check and result.returncode != 0:
        raise sp.CalledProcessError(result.returncode, args, output=result.stdout, stderr=result.stderr)
    return result
