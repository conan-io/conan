"""
Implements core.log:enabled: appends everything a command prints to a file under
<conan_home>/.log. Covers Conan's own messages and formatter output
(conan/api/output.py) and subprocess output (conan/internal/util/runners.py).
"""

import codecs
import os
import re
import threading
from contextlib import contextmanager
from datetime import datetime
from conan.internal.cache.home_paths import HomePaths


class ConanLog:
    """activate() computes log_path once per top-level Cli.run() call; core.log:enabled
    is read before any argument is parsed, so only global.conf is honored, not a `-cc
    core.log:enabled=True` override. set_context() is called later, once the command's
    arguments (e.g. --password) are known, and commits the header on its own first
    call so a nested command can't steal it. The file is opened lazily on first use.
    All writes go through _lock, since Conan prints from several threads at once."""

    log_path = None
    _date = None
    _command = None
    _file = None
    _secrets = []
    _lock = threading.RLock()

    @classmethod
    @contextmanager
    def activate(cls, conan_api, raw_args):
        if not conan_api.config.get("core.log:enabled", default=False, check_type=bool):
            yield
            return
        log_dir = HomePaths(conan_api.home_folder).command_logs_path
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", raw_args[0]) if raw_args else "conan"
        cls._date = datetime.now()
        cls.log_path = os.path.join(
            log_dir, f"{cls._date:%Y%m%d_%H%M%S}_{os.getpid()}_{safe_name}.log")
        try:
            yield
        finally:
            with cls._lock:
                if cls._file is not None:
                    cls._file.close()
                cls.log_path = None
                cls._file = None
                cls._command = None
                cls._secrets = []

    @classmethod
    def set_context(cls, command_name, raw_args, secrets):
        """command_name and raw_args rebuild the command line. secrets are exact
        values redacted wherever they show up."""
        if cls.log_path is None:
            return
        with cls._lock:
            cls._secrets.extend(s for s in (secrets or []) if s)
            if cls._file is None:
                cls._command = " ".join([command_name] + raw_args)
                cls._check_log_file()

    @classmethod
    def _redact(cls, text):
        # TODO: credentials embedded in a URL (scheme://user:pass@host) aren't covered yet
        for secret in cls._secrets:
            text = text.replace(secret, "********")
        return text

    @classmethod
    def _check_log_file(cls):
        """Must be called with _lock already held. Opens the file once, the first time
        something needs to log, and keeps it open for the rest of the command. Returns
        whether cls._file is available to write to."""
        if cls._file is not None:
            return True
        if not cls.log_path:
            return False
        try:
            os.makedirs(os.path.dirname(cls.log_path), exist_ok=True)
            cls._file = open(cls.log_path, "a", encoding="utf-8", errors="replace")
            cls._file.write(f"# Date: {cls._date:%Y-%m-%d %H:%M:%S}\n"
                            f"# Command: {cls._redact(cls._command)}\n"
                            f"{'#' + '-' * 60}\n")
            cls._file.flush()
            return True
        except Exception as e:
            cls.log_path = None
            from conan.api.output import ConanOutput
            ConanOutput().warning(f"core.log:enabled couldn't create the log file: {e}")
            return False

    def stream_subprocess(self, proc, stdout, stderr):
        """Forwards proc's stdout/stderr live, then logs them once it finishes. Either
        pipe can be None: merged into the other, or never captured to begin with (e.g.
        stdout/stderr was subprocess.DEVNULL)."""
        out_chunks, err_chunks = [], []

        def pump(pipe, sink, chunks):
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            with pipe:
                for data in iter(lambda: pipe.read1(4096), b""):
                    chunks.append(data)
                    sink.write(decoder.decode(data))
            pending = decoder.decode(b"", final=True)
            if pending:
                sink.write(pending)

        if proc.stdout is not None and proc.stderr is not None:
            t_err = threading.Thread(target=pump, args=(proc.stderr, stderr, err_chunks))
            t_err.start()
            pump(proc.stdout, stdout, out_chunks)
            t_err.join()
        elif proc.stdout is not None:
            pump(proc.stdout, stdout, out_chunks)
        elif proc.stderr is not None:
            pump(proc.stderr, stderr, err_chunks)
        self.log_subprocess_call(b"".join(out_chunks), b"".join(err_chunks))

    def log_subprocess_call(self, proc_stdout, proc_stderr):
        with self._lock:
            if self._check_log_file():
                try:
                    if proc_stdout:
                        self._file.write(self._redact(proc_stdout.decode("utf-8", errors="replace")))
                    if proc_stderr:
                        self._file.write(self._redact(proc_stderr.decode("utf-8", errors="replace")))
                    self._file.flush()
                except Exception:
                    pass

    def log_message(self, text):
        """Called for every line written to the terminal, both ConanOutput's own
        messages and formatter output through cli_out_write, with the same ANSI
        stripping and redaction as everything else in this module."""
        with self._lock:
            if self._check_log_file():
                try:
                    self._file.write(self._redact(re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)))
                    self._file.flush()
                except Exception:
                    pass
