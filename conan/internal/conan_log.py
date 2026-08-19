"""
Implements core.log:enabled: installs an OutputTee over sys.stdout/sys.stderr for the
duration of a command, so everything shown in the console (including subprocess output,
captured by conan_run() via runners.py) ends up in a file under <conan_home>/.log.
"""

import io
import os
import re
import sys
import threading
from contextlib import contextmanager
from datetime import datetime

from conan.internal.cache.home_paths import HomePaths

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


class LogFile:
    """The log file that receives a copy of everything shown in the console. A single
    instance is shared by the OutputTee wrappers of stdout and stderr, so both streams
    land in the same file, in the order the user actually saw them. Conan prints from
    several threads at once (parallel downloads, uploads, installs), hence the lock."""

    def __init__(self, path):
        self._file = open(path, "w", encoding="utf-8", errors="replace", newline="")
        self._lock = threading.Lock()
        self.secrets = []

    def redact(self, text):
        for secret in self.secrets:
            text = text.replace(secret, "********")
        return text

    def write(self, data):
        data = self.redact(_ANSI_ESCAPE_RE.sub("", data))
        if not data:
            return
        with self._lock:
            if self._file.closed:
                return
            self._file.write(data)
            self._file.flush()

    def close(self):
        with self._lock:
            self._file.close()


class OutputTee:
    """Wraps sys.stdout/sys.stderr so everything written to them is also copied to a
    LogFile. This happens at the Python level, not by duplicating file descriptors, so
    isatty() keeps answering for the real console and colors are not lost."""

    def __init__(self, stream, log_file):
        self._stream = stream
        self._log = log_file

    def write(self, data):
        ret = self._stream.write(data)
        self._stream.flush()
        self._log.write(data)
        return ret

    def flush(self):
        self._stream.flush()

    def isatty(self):
        return hasattr(self._stream, "isatty") and self._stream.isatty()

    def fileno(self):
        # Not the descriptor of the console: writing to it would skip the log. This is
        # also what tells conan_run() this stream needs piping to be captured
        raise io.UnsupportedOperation("fileno")

    def __getattr__(self, name):
        if name.startswith("_"):  # never delegate internals, would recurse on _stream
            raise AttributeError(name)
        return getattr(self._stream, name)


class ConanLog:
    """config() is called once per command dispatch, from ConanArgumentParser.parse_args(),
    with core.log:enabled read through conan_api.config: this way it sees --core-conf
    overrides and a custom ConanAPI(cache_folder=...). A no-op while nested(): a command
    calling another one in the same process shares the outer command's log instead of
    installing its own."""

    _log_file = None
    _saved_stdout = None
    _saved_stderr = None
    _nesting = 0

    @classmethod
    def config(cls, enabled, home, command_name, raw_args, secrets=None):
        if cls._nesting > 0:
            return
        cls._teardown()
        if not enabled:
            return
        log_dir = HomePaths(home).command_logs_path
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", command_name)
        now = datetime.now()
        path = os.path.join(log_dir, f"{now:%Y%m%d_%H%M%S}_{os.getpid()}_{safe_name}.log")
        try:
            os.makedirs(log_dir, exist_ok=True)
            log_file = LogFile(path)
        except Exception as e:
            from conan.api.output import ConanOutput
            ConanOutput().warning(f"core.log:enabled couldn't create the log file: {e}")
            return
        log_file.secrets = [s for s in (secrets or []) if s]
        log_file.write(f"# Date: {now:%Y-%m-%d %H:%M:%S}\n"
                       f"# Command: {log_file.redact(' '.join([command_name] + raw_args))}\n"
                       f"{'#' + '-' * 60}\n")
        cls._log_file = log_file
        cls._saved_stdout, cls._saved_stderr = sys.stdout, sys.stderr
        sys.stdout = OutputTee(sys.stdout, log_file)
        sys.stderr = OutputTee(sys.stderr, log_file)

    @classmethod
    def _teardown(cls):
        if cls._log_file is not None:
            sys.stdout, sys.stderr = cls._saved_stdout, cls._saved_stderr
            cls._log_file.close()
            cls._log_file = None

    @classmethod
    @contextmanager
    def nested(cls):
        """Used by CommandAPI.run() when a command calls another one in the same
        process, so the nested command's own config() call is a no-op."""
        cls._nesting += 1
        try:
            yield
        finally:
            cls._nesting -= 1
