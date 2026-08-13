import os
import re

from conan.api.conan_api import ConanAPI
from conan.cli.command_log import command_log_context
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
    assert re.search(r"# Duration: \d+\.\d+s\n", content)
    assert "# Exit code: 0 (SUCCESS)" in content


def test_exit_code_name_for_known_error_code():
    conan_api = _make_conan_api("core.log:enabled=True")
    with command_log_context(conan_api, ["install", "."]) as log_ctx:
        log_ctx.set_exit_code(1)
    log_dir = HomePaths(conan_api.home_folder).command_logs_path
    content = open(os.path.join(log_dir, os.listdir(log_dir)[0])).read()
    assert "# Exit code: 1 (ERROR_GENERAL)" in content


def test_env_vars_default_list_records_set_vars_only(monkeypatch):
    monkeypatch.setenv("CC", "/usr/bin/gcc")
    monkeypatch.delenv("CXX", raising=False)
    conan_api = _make_conan_api("core.log:enabled=True")
    with command_log_context(conan_api, ["install", "."]) as log_ctx:
        log_ctx.set_exit_code(0)
    log_dir = HomePaths(conan_api.home_folder).command_logs_path
    content = open(os.path.join(log_dir, os.listdir(log_dir)[0])).read()
    assert "# Env CC: /usr/bin/gcc\n" in content
    assert "# Env CXX:" not in content


def test_log_file_name_defaults_to_conan_when_no_args():
    conan_api = _make_conan_api("core.log:enabled=True")
    with command_log_context(conan_api, []) as log_ctx:
        log_ctx.set_exit_code(0)
    log_dir = HomePaths(conan_api.home_folder).command_logs_path
    log_files = os.listdir(log_dir)
    assert len(log_files) == 1
    assert log_files[0].endswith("_conan.log")


def test_log_file_name_includes_pid_to_avoid_collisions():
    conan_api = _make_conan_api("core.log:enabled=True")
    with command_log_context(conan_api, ["install", "."]) as log_ctx:
        log_ctx.set_exit_code(0)
    log_dir = HomePaths(conan_api.home_folder).command_logs_path
    log_files = os.listdir(log_dir)
    assert len(log_files) == 1
    assert f"_{os.getpid()}_install.log" in log_files[0]


def test_remote_login_password_is_redacted_from_command_line():
    conan_api = _make_conan_api("core.log:enabled=True")
    with command_log_context(conan_api, ["remote", "login", "myremote", "user", "-p",
                                          "supersecret"]) as log_ctx:
        log_ctx.set_exit_code(0)
    log_dir = HomePaths(conan_api.home_folder).command_logs_path
    content = open(os.path.join(log_dir, os.listdir(log_dir)[0])).read()
    assert "supersecret" not in content
    assert "# Command: conan remote login myremote user -p ********\n" in content


def test_audit_provider_token_is_redacted_from_command_line():
    conan_api = _make_conan_api("core.log:enabled=True")
    with command_log_context(conan_api, ["audit", "provider", "auth", "myprovider",
                                          "--token=supersecret"]) as log_ctx:
        log_ctx.set_exit_code(0)
    log_dir = HomePaths(conan_api.home_folder).command_logs_path
    content = open(os.path.join(log_dir, os.listdir(log_dir)[0])).read()
    assert "supersecret" not in content
    assert "--token=********" in content


def test_unrelated_package_query_short_flag_is_not_redacted():
    conan_api = _make_conan_api("core.log:enabled=True")
    with command_log_context(conan_api, ["list", "-p", "os=Windows"]) as log_ctx:
        log_ctx.set_exit_code(0)
    log_dir = HomePaths(conan_api.home_folder).command_logs_path
    content = open(os.path.join(log_dir, os.listdir(log_dir)[0])).read()
    assert "# Command: conan list -p os=Windows\n" in content
