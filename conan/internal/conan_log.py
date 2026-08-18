"""
Implements core.log:enabled: appends everything a command prints to a file under
<conan_home>/.log. Covers Conan's own messages and formatter output
(conan/api/output.py) and subprocess output (conan/internal/util/runners.py).
"""

import os
import re
import sys
from datetime import datetime

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
    """conan_log is created when this module is imported. Resolving core.log:enabled and
    creating the log file is deferred to the first access to log_path, since this module
    loads as part of conan/api/output.py, before conan.internal.model.conf can be
    imported."""

    def __init__(self):
        self._resolved = False
        self._log_path = None

    @property
    def log_path(self):
        if self._resolved:
            return self._log_path
        self._resolved = True
        try:
            from conan.internal.model.conf import load_global_conf
            from conan.internal.paths import get_conan_user_home

            home = get_conan_user_home()
            enabled = load_global_conf(home).get("core.log:enabled", default=False,
                                                  check_type=bool)
            if not enabled:
                return None

            log_dir = os.path.join(home, ".log")
            os.makedirs(log_dir, exist_ok=True)
            command_name = sys.argv[1] if len(sys.argv) > 1 else "conan"
            safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", command_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(log_dir, f"{timestamp}_{os.getpid()}_{safe_name}.log")
            with open(path, "w", encoding="utf-8", errors="replace") as f:
                f.write(
                    f"# Date: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
                    f"# Command: conan {_redact(' '.join(sys.argv[1:]))}\n"
                    f"# PID: {os.getpid()}\n"
                    f"{_SEPARATOR}"
                )
            self._log_path = path
        except Exception:
            self._log_path = None
        return self._log_path

    def log_subprocess_call(self, proc_stdout, proc_stderr):
        if not self._log_path:
            return
        try:
            with open(self._log_path, "a", encoding="utf-8", errors="replace") as f:
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
        if self.log_path is None:
            return
        try:
            with open(self._log_path, "a", encoding="utf-8", errors="replace") as f:
                f.write(_redact(_ANSI_ESCAPE_RE.sub("", text)))
        except Exception:
            pass


conan_log = ConanLog()
