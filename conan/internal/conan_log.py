import contextlib
import os
import platform
import re
import sys
import threading
from datetime import datetime

from conan import __version__
from conan.cli import exit_codes
from conan.internal.cache.home_paths import HomePaths

_ANSI_ESCAPE_RE = re.compile(rb"\x1b\[[0-9;]*[a-zA-Z]")
_EXIT_CODE_NAMES = {value: name for name, value in vars(exit_codes).items()
                    if name.isupper() and isinstance(value, int)}
_DEFAULT_ENV_VARS = ["CC", "CXX", "CFLAGS", "CXXFLAGS", "LDFLAGS", "PATH"]
_SEPARATOR = "#" + "-" * 60 + "\n"


def _open_duplicated_fd():
    if platform.system() == "Windows":
        # Windows has no pty equivalent in the standard library, so the duplicated fd is a
        # plain pipe: it always reports isatty()=False, so colors are lost while logging
        # is enabled here, unlike on POSIX where a pty preserves them.
        return os.pipe()
    # A pty makes the duplicated fd report isatty()=True, same as the real terminal, so
    # Conan's and every subprocess' own ANSI colors keep working while logging. Only called
    # when the original fd already was a real terminal (see caller): using one when the
    # original was redirected/piped would start emitting colors where there weren't any.
    import pty
    import tty
    read_fd, write_fd = pty.openpty()
    tty.setraw(write_fd)  # disable line buffering/echo/CRLF translation
    return read_fd, write_fd


def _redact_command_line(args):
    # "-p" only carries a secret for "conan remote login"
    secret_flags = {"--password", "--token"}
    if args[:2] == ["remote", "login"]:
        secret_flags.add("-p")

    redacted = list(args)
    for i, arg in enumerate(args):
        key, sep, _ = arg.partition("=")
        if key not in secret_flags:
            continue
        if sep:
            redacted[i] = f"{key}=********"
        # nargs='?' flags may have no value: a following "-..." token is the next
        # flag, not the secret, so only redact a following token that isn't one.
        elif i + 1 < len(args) and not args[i + 1].startswith("-"):
            redacted[i + 1] = "********"
    return redacted


class _NullCommandLogger:
    def set_exit_code(self, exit_code):
        pass


class _TeeCommandLogger:
    # fd-level duplication (not just sys.stdout/stderr) so subprocess output
    # (cmake, make, git...) is captured too, since it bypasses ConanOutput.
    def __init__(self, log_path, command_line, home_folder):
        self._file = open(log_path, "w", encoding="utf-8", errors="replace")
        self._lock = threading.Lock()
        self._exit_code = None
        self._start = datetime.now()
        env_lines = "".join(f"# Env {name}: {os.environ[name]}\n" for name in _DEFAULT_ENV_VARS
                            if name in os.environ)
        self._file.write(
            f"# Date: {self._start:%Y-%m-%d %H:%M:%S}\n"
            f"# Command: {command_line}\n"
            f"# Conan version: {__version__}\n"
            f"# Conan home: {home_folder}\n"
            f"# Working directory: {os.getcwd()}\n"
            f"# Platform: {platform.platform()}\n"
            f"{env_lines}{_SEPARATOR}"
        )
        self._file.flush()

        self._saved_fds = {}
        self._threads = []
        for fd in (1, 2):
            self._saved_fds[fd] = os.dup(fd)
            # Only duplicate via the terminal-preserving trick if the original stream
            # already was a real terminal - using it when the original was redirected/piped
            # would start emitting ANSI colors where there weren't any before.
            read_fd, write_fd = _open_duplicated_fd() if os.isatty(fd) else os.pipe()
            os.dup2(write_fd, fd)
            os.close(write_fd)
            thread = threading.Thread(target=self._pump, args=(read_fd, self._saved_fds[fd]),
                                       daemon=True)
            thread.start()
            self._threads.append(thread)

    def _pump(self, read_fd, terminal_fd):
        while True:
            try:
                chunk = os.read(read_fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            os.write(terminal_fd, chunk)
            clean = _ANSI_ESCAPE_RE.sub(b"", chunk)
            with self._lock:
                self._file.write(clean.decode("utf-8", errors="replace"))
                self._file.flush()
        os.close(read_fd)

    def set_exit_code(self, exit_code):
        self._exit_code = exit_code

    def close(self):
        sys.stdout.flush()
        sys.stderr.flush()
        # dup2 closes the pipe write end, so pump threads drain it and exit;
        # only close saved_fd afterwards, since they still write to it.
        for fd, saved_fd in self._saved_fds.items():
            os.dup2(saved_fd, fd)
        for thread in self._threads:
            thread.join(timeout=5)
        for saved_fd in self._saved_fds.values():
            os.close(saved_fd)
        with self._lock:
            exit_code_name = _EXIT_CODE_NAMES.get(self._exit_code)
            suffix = f" ({exit_code_name})" if exit_code_name else ""
            self._file.write(
                f"{_SEPARATOR}"
                f"# Duration: {(datetime.now() - self._start).total_seconds():.1f}s\n"
                f"# Exit code: {self._exit_code}{suffix}\n"
            )
            self._file.close()


@contextlib.contextmanager
def command_log_context(conan_api, args):
    enabled = conan_api.config.get("core.log:enabled", default=False, check_type=bool)
    if not enabled:
        yield _NullCommandLogger()
        return

    log_dir = HomePaths(conan_api.home_folder).command_logs_path
    os.makedirs(log_dir, exist_ok=True)

    command_name = args[0] if args else "conan"
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", command_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_dir, f"{timestamp}_{os.getpid()}_{safe_name}.log")
    command_line = "conan " + " ".join(_redact_command_line(args))

    logger = _TeeCommandLogger(log_path, command_line, conan_api.home_folder)
    try:
        yield logger
    finally:
        logger.close()
