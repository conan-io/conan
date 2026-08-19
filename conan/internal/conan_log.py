"""
Implements core.log:enabled: appends everything a command prints to a file under
<conan_home>/.log. Covers Conan's own messages and formatter output
(conan/api/output.py) and subprocess output (conan/internal/util/runners.py).
"""

import codecs
import os
import re
import threading
from datetime import datetime
from conan.internal.cache.home_paths import HomePaths

_SEPARATOR = "#" + "-" * 60 + "\n"
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_SECRET_FLAGS = {"--password", "--token", "-p"}


def _redact(text):
    lines = []
    for line in str(text).split("\n"):
        if not any(flag in line for flag in _SECRET_FLAGS) and "://" not in line:
            lines.append(line)
            continue

        tokens = line.split(" ")
        redacted = list(tokens)
        for i, token in enumerate(tokens):
            key, sep, _ = token.partition("=")
            if key in _SECRET_FLAGS:
                if sep:
                    redacted[i] = f"{key}=********"
                elif i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                    redacted[i + 1] = "********"
                continue
            # scheme://user:password@host
            scheme = token.find("://")
            if scheme == -1:
                continue
            at = token.find("@", scheme + 3)
            colon = token.find(":", scheme + 3)
            if at != -1 and colon != -1 and colon < at:
                redacted[i] = token[:colon + 1] + "********" + token[at:]
        lines.append(" ".join(redacted))
    return "\n".join(lines)


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
    _lock = threading.RLock()

    @classmethod
    def config(cls, enabled, home, command_name, raw_args):
        """command_name plus raw_args (the args the parser received, before parsing)
        rebuild the actual command line."""
        if cls._file is not None:
            try:
                cls._file.close()
            except Exception:
                pass
        cls.log_path = None
        cls._file = None
        if not enabled:
            return
        log_dir = HomePaths(home).command_logs_path
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", command_name)
        cls._date = datetime.now()
        cls._command = " ".join([command_name] + raw_args)
        cls.log_path = os.path.join(
            log_dir, f"{cls._date:%Y%m%d_%H%M%S}_{os.getpid()}_{safe_name}.log")

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
                            f"# Command: {_redact(cls._command)}\n"
                            f"{_SEPARATOR}")
            cls._file.flush()
            return True
        except Exception as e:
            cls.log_path = None
            from conan.api.output import ConanOutput
            ConanOutput().warning(f"core.log:enabled couldn't create the log file: {e}")
            return False

    def stream_subprocess(self, proc, stdout, stderr):
        """Forwards proc's stdout/stderr live, then logs them once it finishes.
        proc.stderr is None when merged into stdout, read as a single stream to
        preserve their real order."""
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

        if proc.stderr is None:
            pump(proc.stdout, stdout, out_chunks)
        else:
            t_err = threading.Thread(target=pump, args=(proc.stderr, stderr, err_chunks))
            t_err.start()
            pump(proc.stdout, stdout, out_chunks)
            t_err.join()
        self.log_subprocess_call(b"".join(out_chunks), b"".join(err_chunks))

    def log_subprocess_call(self, proc_stdout, proc_stderr):
        with self._lock:
            if self._check_log_file():
                try:
                    if proc_stdout:
                        self._file.write(_redact(proc_stdout.decode("utf-8", errors="replace")))
                    if proc_stderr:
                        self._file.write(_redact(proc_stderr.decode("utf-8", errors="replace")))
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
                    self._file.write(_redact(_ANSI_ESCAPE_RE.sub("", text)))
                    self._file.flush()
                except Exception:
                    pass
