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
    """config() must be called once per command, normally from
    ConanArgumentParser.parse_args(), with core.log:enabled read through conan_api.config.
    log_path is set right away; the file itself, kept open for the whole command once
    created, is only opened on first use. All writes go through _lock, since Conan prints
    from several threads at once (parallel downloads, uploads, installs)."""

    log_path = None
    _date = None
    _command = None
    _file = None
    _secrets = []
    _nesting = 0
    _lock = threading.RLock()

    @classmethod
    def config(cls, enabled, home, command_name, raw_args, secrets=None):
        """command_name and raw_args rebuild the command line. secrets are exact
        values redacted wherever they show up. A no-op while nested(): a command
        calling another one in the same process shares the outer command's log."""
        if cls._nesting > 0:
            return
        if cls._file is not None:
            try:
                cls._file.close()
            except Exception:
                pass
        cls.log_path = None
        cls._file = None
        cls._secrets = [s for s in (secrets or []) if s]
        if not enabled:
            return
        log_dir = HomePaths(home).command_logs_path
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", command_name)
        cls._date = datetime.now()
        cls._command = " ".join([command_name] + raw_args)
        cls.log_path = os.path.join(
            log_dir, f"{cls._date:%Y%m%d_%H%M%S}_{os.getpid()}_{safe_name}.log")

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
