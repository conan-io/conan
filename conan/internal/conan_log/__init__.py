import contextlib
import os
import platform
import re
import sys
import threading
from datetime import datetime
from io import StringIO

from conan import __version__
from conan.cli import exit_codes
from conan.errors import ConanException
from conan.internal.cache.home_paths import HomePaths

_ANSI_ESCAPE_RE = re.compile(rb"\x1b\[[0-9;]*[a-zA-Z]")
_EXIT_CODE_NAMES = {value: name for name, value in vars(exit_codes).items()
                    if name.isupper() and isinstance(value, int)}
_DEFAULT_ENV_VARS = ["CC", "CXX", "CFLAGS", "CXXFLAGS", "LDFLAGS", "PATH"]
_SEPARATOR = "#" + "-" * 60 + "\n"


def win_log_run(command, stdout, stderr, cwd, shell=True):
    """On Windows, while neither stream is an explicit StringIO, runs `command` via ConPTY
    instead of Popen so it keeps its native colors while still being capturable. Called by
    conan_run() only when its caller says core.log:enabled is set.

    EXPERIMENTAL, see win_conpty.py.

    :return: the subprocess return code, or None if this doesn't apply (wrong platform, or
        an explicit StringIO capture in play). The caller falls back to Popen.
    """
    if platform.system() != "Windows" or isinstance(stdout, StringIO) \
            or isinstance(stderr, StringIO):
        return None

    from conan.internal.conan_log.win_conpty import run_in_pseudo_console
    try:
        _, returncode = run_in_pseudo_console(command, cwd=cwd, shell=shell)
    except Exception as e:
        raise ConanException("Error while running cmd\nError: %s" % (str(e)))
    return returncode


def _open_duplicated_fd(fd):
    if platform.system() == "Windows" or not os.isatty(fd):
        # No pty on Windows; also the right fallback when fd isn't a real terminal.
        return os.pipe()
    # A pty makes the duplicate report isatty()=True too, so colors keep working.
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
        # A following "-..." token is the next flag, not the value, so leave it.
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
            read_fd, write_fd = _open_duplicated_fd(fd)
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
