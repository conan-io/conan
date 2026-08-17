"""
EXPERIMENTAL.

Uses pywinpty, a Windows-only dependency, to attach a subprocess to a ConPTY pseudo-console
so it keeps its native colors while still being capturable. Windows attaches a process to a
pseudo-console per spawn, unlike the POSIX pty in __init__.py, which is set up once and
inherited by every subprocess for free. That's why conan_run() (runners.py) calls this
directly per subprocess instead of once per command.
"""

import os

from winpty import PtyProcess


def run_in_pseudo_console(command, cwd=None):
    """Spawns `command` attached to a pseudo-console, so it keeps its native ANSI colors.
    Combines stdout+stderr into one stream (like a real console), echoes it live to fd 1,
    and also returns it so conan_run() can feed it to the command log.

    :return: (captured_text, returncode)
    """
    cmdline = command if isinstance(command, str) else " ".join(command)
    proc = PtyProcess.spawn(cmdline, cwd=cwd)

    chunks = []
    while proc.isalive():
        try:
            chunk = proc.read(4096)
        except EOFError:
            break
        if not chunk:
            continue
        data = chunk.encode("utf-8", errors="replace") if isinstance(chunk, str) else chunk
        # The child writes into pywinpty's own console, not conan's fd 1,
        # so this is the only way the user sees it live and since fd 1 is already
        # dup2()'d to the log's pipe here (_TeeCommandLogger, __init__.py), it's also how
        # the log file gets it.
        os.write(1, data)
        chunks.append(chunk)

    proc.wait()
    captured = "".join(c if isinstance(c, str) else c.decode("utf-8", errors="replace")
                       for c in chunks)
    return captured, proc.exitstatus
