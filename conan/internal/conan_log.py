"""
Implements core.log:enabled: appends everything a command prints to a file under
<conan_home>/.log. Covers Conan's own messages and formatter output
(conan/api/output.py) and subprocess output (conan/internal/util/runners.py).
"""

import codecs
import os
import re
import sys
import threading
from datetime import datetime
from conan.internal.cache.home_paths import HomePaths

_SEPARATOR = "#" + "-" * 60 + "\n"
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_SECRET_FLAGS = {"--password", "--token"}


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
    log_path is set right away; the file and its header are only created on first use."""

    log_path = None
    _date = None
    _command = None

    @classmethod
    def config(cls, enabled, home):
        cls.log_path = None
        if not enabled:
            return
        log_dir = HomePaths(home).command_logs_path
        command_name = sys.argv[1] if len(sys.argv) > 1 else "conan"
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", command_name)
        cls._date = datetime.now()
        cls._command = " ".join(sys.argv[1:])
        cls.log_path = os.path.join(
            log_dir, f"{cls._date:%Y%m%d_%H%M%S}_{os.getpid()}_{safe_name}.log")

    @classmethod
    def _log_file(cls):
        if not cls.log_path or os.path.exists(cls.log_path):
            return cls.log_path
        try:
            os.makedirs(os.path.dirname(cls.log_path), exist_ok=True)
            with open(cls.log_path, "w", encoding="utf-8", errors="replace") as f:
                f.write(f"# Date: {cls._date:%Y-%m-%d %H:%M:%S}\n"
                       f"# Command: conan {_redact(cls._command)}\n"
                       f"{_SEPARATOR}")
        except Exception:
            cls.log_path = None
        return cls.log_path

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
        if not self._log_file():
            return
        try:
            with open(self.log_path, "a", encoding="utf-8", errors="replace") as f:
                if proc_stdout:
                    f.write(_redact(proc_stdout.decode("utf-8", errors="replace")))
                if proc_stderr:
                    f.write(_redact(proc_stderr.decode("utf-8", errors="replace")))
        except Exception:
            pass

    def log_message(self, text):
        """Called for every line written to the terminal, both ConanOutput's own
        messages and formatter output through cli_out_write, with the same ANSI
        stripping and redaction as everything else in this module."""
        if not self._log_file():
            return
        try:
            with open(self.log_path, "a", encoding="utf-8", errors="replace") as f:
                f.write(_redact(_ANSI_ESCAPE_RE.sub("", text)))
        except Exception:
            pass
