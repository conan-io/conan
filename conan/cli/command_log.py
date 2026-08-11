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


def _timestamp():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


class _NullCommandLogger:
    def set_exit_code(self, exit_code):
        pass


class _TeeCommandLogger:
    # fd-level duplication (not just sys.stdout/stderr) so subprocess output
    # (cmake, make, git...) is captured too, since it bypasses ConanOutput.
    def __init__(self, log_path, command_line, home_folder, timestamps, env_vars):
        self._file = open(log_path, "w", encoding="utf-8", errors="replace")
        self._lock = threading.Lock()
        self._exit_code = None
        self._timestamps = timestamps
        self._start = datetime.now()
        self._file.write(f"# Date: {self._start:%Y-%m-%d %H:%M:%S}\n")
        self._file.write(f"# Command: {command_line}\n")
        self._file.write(f"# Conan version: {__version__}\n")
        self._file.write(f"# Conan home: {home_folder}\n")
        self._file.write(f"# Working directory: {os.getcwd()}\n")
        self._file.write(f"# Platform: {platform.platform()}\n")
        for name in env_vars:
            if name in os.environ:
                self._file.write(f"# Env {name}: {os.environ[name]}\n")
        self._file.write("#" + "-" * 60 + "\n")
        self._file.flush()

        self._saved_fds = {}
        self._read_fds = []
        self._threads = []
        for fd in (1, 2):
            self._saved_fds[fd] = os.dup(fd)
            read_fd, write_fd = os.pipe()
            os.dup2(write_fd, fd)
            os.close(write_fd)
            self._read_fds.append(read_fd)
            thread = threading.Thread(target=self._pump, args=(read_fd, self._saved_fds[fd]),
                                       daemon=True)
            thread.start()
            self._threads.append(thread)

    def _pump(self, read_fd, terminal_fd):
        buffer = b""
        while True:
            try:
                chunk = os.read(read_fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            os.write(terminal_fd, chunk)
            clean = _ANSI_ESCAPE_RE.sub(b"", chunk)
            if not self._timestamps:
                with self._lock:
                    self._file.write(clean.decode("utf-8", errors="replace"))
                    self._file.flush()
                continue
            # Timestamps are per-line, but chunks don't align with line
            # boundaries, so buffer whatever's left until the next '\n'.
            buffer += clean
            *lines, buffer = buffer.split(b"\n")
            if lines:
                with self._lock:
                    for line in lines:
                        self._file.write(f"[{_timestamp()}] {line.decode('utf-8', errors='replace')}\n")
                    self._file.flush()
        if self._timestamps and buffer:
            with self._lock:
                self._file.write(f"[{_timestamp()}] {buffer.decode('utf-8', errors='replace')}\n")
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
            self._file.write("#" + "-" * 60 + "\n")
            self._file.write(f"# Duration: {(datetime.now() - self._start).total_seconds():.1f}s\n")
            exit_code_name = _EXIT_CODE_NAMES.get(self._exit_code)
            suffix = f" ({exit_code_name})" if exit_code_name else ""
            self._file.write(f"# Exit code: {self._exit_code}{suffix}\n")
            self._file.close()


def _cleanup_old_logs(log_dir, max_age_days, max_files):
    entries = [os.path.join(log_dir, name) for name in os.listdir(log_dir)
               if name.endswith(".log")]
    if max_age_days:
        threshold = datetime.now().timestamp() - max_age_days * 86400
        kept = []
        for path in entries:
            if os.path.getmtime(path) < threshold:
                os.remove(path)
            else:
                kept.append(path)
        entries = kept
    if max_files and len(entries) > max_files:
        entries.sort(key=os.path.getmtime)
        for path in entries[:len(entries) - max_files]:
            os.remove(path)


@contextlib.contextmanager
def command_log_context(conan_api, args):
    enabled = conan_api.config.get("core.log:enabled", default=False, check_type=bool)
    if not enabled:
        yield _NullCommandLogger()
        return

    log_dir = HomePaths(conan_api.home_folder).command_logs_path
    os.makedirs(log_dir, exist_ok=True)
    max_age_days = conan_api.config.get("core.log:max_age_days", default=30, check_type=int)
    max_files = conan_api.config.get("core.log:max_files", default=200, check_type=int)
    _cleanup_old_logs(log_dir, max_age_days, max_files - 1 if max_files else max_files)

    command_name = args[0] if args else "conan"
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", command_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_dir, f"{timestamp}_{safe_name}.log")
    command_line = "conan " + " ".join(args)

    timestamps = conan_api.config.get("core.log:timestamps", default=False, check_type=bool)
    env_vars = conan_api.config.get("core.log:env_vars", default=_DEFAULT_ENV_VARS, check_type=list)

    logger = _TeeCommandLogger(log_path, command_line, conan_api.home_folder, timestamps, env_vars)
    try:
        yield logger
    finally:
        logger.close()
