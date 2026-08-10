import os
import time

from conan.api.conan_api import ConanAPI
from conan.cli.command_log import _cleanup_old_logs, command_log_context
from conan.internal.cache.home_paths import HomePaths
from conan.internal.util.files import save
from conan.test.utils.test_files import temp_folder


def _make_conan_api(global_conf_contents=""):
    tmp_folder = temp_folder()
    home_paths = HomePaths(tmp_folder)
    save(os.path.join(home_paths.profiles_path, "default"), "")
    save(home_paths.global_conf_path, global_conf_contents)
    return ConanAPI(tmp_folder)


def test_disabled_by_default_yields_null_logger():
    conan_api = _make_conan_api()
    with command_log_context(conan_api, ["--version"]) as log_ctx:
        log_ctx.set_exit_code(0)  # no-op, must not raise
    log_dir = HomePaths(conan_api.home_folder).command_logs_path
    assert not os.path.exists(log_dir)


def test_enabled_writes_header_output_and_footer():
    conan_api = _make_conan_api("core.log:enabled=True")
    with command_log_context(conan_api, ["install", "."]) as log_ctx:
        os.write(1, b"hello stdout\n")
        os.write(2, b"\x1b[31mhello stderr\x1b[0m\n")
        log_ctx.set_exit_code(0)

    log_dir = HomePaths(conan_api.home_folder).command_logs_path
    log_files = os.listdir(log_dir)
    assert len(log_files) == 1
    assert log_files[0].endswith("_install.log")

    content = open(os.path.join(log_dir, log_files[0])).read()
    assert "# Command: conan install .\n" in content
    assert f"# Conan home: {conan_api.home_folder}\n" in content
    assert "# Conan version:" in content
    assert "# Working directory:" in content
    assert "# Platform:" in content
    assert "hello stdout" in content
    assert "hello stderr" in content
    assert "\x1b" not in content  # ANSI color codes stripped
    assert "# Exit code: 0" in content


def test_log_file_name_defaults_to_conan_when_no_args():
    conan_api = _make_conan_api("core.log:enabled=True")
    with command_log_context(conan_api, []) as log_ctx:
        log_ctx.set_exit_code(0)
    log_dir = HomePaths(conan_api.home_folder).command_logs_path
    log_files = os.listdir(log_dir)
    assert len(log_files) == 1
    assert log_files[0].endswith("_conan.log")


def test_cleanup_by_max_files(tmp_path):
    for i in range(5):
        (tmp_path / f"file{i}.log").write_text("x")
    _cleanup_old_logs(str(tmp_path), max_age_days=0, max_files=3)
    remaining = os.listdir(tmp_path)
    assert len(remaining) == 3


def test_cleanup_by_max_age(tmp_path):
    old_file = tmp_path / "old.log"
    old_file.write_text("x")
    old_timestamp = time.time() - 40 * 86400
    os.utime(old_file, (old_timestamp, old_timestamp))

    new_file = tmp_path / "new.log"
    new_file.write_text("x")

    _cleanup_old_logs(str(tmp_path), max_age_days=30, max_files=0)
    remaining = os.listdir(tmp_path)
    assert remaining == ["new.log"]
