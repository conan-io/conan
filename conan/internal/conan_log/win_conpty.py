"""
EXPERIMENTAL.

Uses pywinpty, a Windows-only dependency, to attach a subprocess to a ConPTY pseudo-console
so it keeps its native colors while still being capturable. Windows attaches a process to a
pseudo-console per spawn, unlike the POSIX pty in __init__.py, which is set up once and
inherited by every subprocess for free. That's why conan_run() (runners.py) calls this
directly per subprocess instead of once per command.

Builds the cmdline by hand and calls the low-level PTY class instead of the public
PtyProcess.spawn(): that one always runs every argument after the first through
subprocess.list2cmdline(), which backslash-escapes embedded quotes the way a normal Win32
program expects. cmd.exe's own "/c" parsing doesn't understand that escaping, so a command
that already contains quotes (a quoted path, for example) gets cut off. Building the
cmdline ourselves the same way subprocess.Popen(shell=True) does avoids that mismatch.
"""

import os
import subprocess
from shutil import which

from winpty import PTY, PtyProcess


def _spawn(exe, cmdline, cwd):
    """Replicates PtyProcess.spawn(), minus the subprocess.list2cmdline() call it makes on
    every argument after the first (see module docstring for why that breaks a cmdline
    that already contains quotes). Takes the already-built exe/cmdline instead of an argv."""
    exe_path = which(exe)
    if exe_path is None:
        raise FileNotFoundError(f"The command was not found or was not executable: {exe}.")

    env = "\0".join(f"{k}={v}" for k, v in os.environ.items()) + "\0"
    cwd = cwd or os.getcwd()
    # Low-level PTY, not PtyProcess.spawn(): lets us pass our own pre-built cmdline untouched.
    pty = PTY(80, 24)
    if cmdline is not None:
        pty.spawn(exe_path, cwd=cwd, env=env, cmdline=cmdline)
    else:
        pty.spawn(exe_path, cwd=cwd, env=env)
    return PtyProcess(pty)


def run_in_pseudo_console(command, cwd=None, shell=True):
    """Spawns `command` attached to a pseudo-console, so it keeps its native ANSI colors.
    Combines stdout+stderr into one stream (like a real console), echoes it live to fd 1,
    and also returns it so conan_run() can feed it to the command log.

    :return: (captured_text, returncode)
    """
    if shell:
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        inner = command if isinstance(command, str) else subprocess.list2cmdline(command)
        exe, cmdline = comspec, f' /c "{inner}"'
    else:
        argv = [command] if isinstance(command, str) else list(command)
        exe = argv[0]
        cmdline = f" {subprocess.list2cmdline(argv[1:])}" if len(argv) > 1 else None

    proc = _spawn(exe, cmdline, cwd)

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
