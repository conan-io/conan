import os
import threading

from conan.internal.conan_log import ConanLog, _redact
from conan.test.utils.test_files import temp_folder


def test_redact_password_and_token_flags():
    assert _redact("conan remote login myremote user --password topsecret") == \
           "conan remote login myremote user --password ********"
    assert _redact("conan remote login myremote user -p topsecret") == \
           "conan remote login myremote user -p ********"
    assert _redact("conan remote login myremote user --password=topsecret") == \
           "conan remote login myremote user --password=********"
    assert _redact("conan audit provider auth myprovider --token=abc123") == \
           "conan audit provider auth myprovider --token=********"


def test_redact_url_credentials():
    text = "Uploading to https://myuser:mysecret@example.com/repo.git"
    assert "mysecret" not in _redact(text)
    assert "https://myuser:********@example.com/repo.git" in _redact(text)


def test_redact_leaves_unrelated_text_untouched():
    text = "hello/1.0: Building package\nsome/1.0: Nothing to redact here"
    assert _redact(text) == text


def test_config_disabled_by_default():
    ConanLog.config(False, temp_folder(), "conan create", ["."])
    assert ConanLog.log_path is None


def test_config_creates_file_lazily():
    home = temp_folder()
    ConanLog.config(True, home, "conan create", ["."])
    log_path = ConanLog.log_path
    assert log_path is not None
    assert not os.path.exists(log_path)

    ConanLog().log_message("hello\n")
    assert os.path.exists(log_path)
    content = open(log_path, encoding="utf-8").read()
    assert "# Command: conan create ." in content
    assert "hello" in content


def test_config_resets_state_per_command():
    home = temp_folder()
    ConanLog.config(True, home, "conan profile", ["detect"])
    ConanLog().log_message("first command\n")
    first_path = ConanLog.log_path

    ConanLog.config(True, home, "conan install", ["."])
    second_path = ConanLog.log_path
    assert second_path != first_path
    ConanLog().log_message("second command\n")

    assert "first command" in open(first_path, encoding="utf-8").read()
    assert "second command" in open(second_path, encoding="utf-8").read()
    assert "second command" not in open(first_path, encoding="utf-8").read()


def test_config_rebuilds_command_line_from_prog_and_raw_args():
    home = temp_folder()
    ConanLog.config(True, home, "conan create", [".", "-cc", "core.log:enabled=True"])
    ConanLog().log_message("hello\n")
    content = open(ConanLog.log_path, encoding="utf-8").read()
    assert "# Command: conan create . -cc core.log:enabled=True" in content


def test_concurrent_writes_are_not_lost():
    home = temp_folder()
    ConanLog.config(True, home, "conan create", ["."])

    def worker(n):
        for i in range(200):
            ConanLog().log_message(f"thread{n}-line{i}\n")

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = open(ConanLog.log_path, encoding="utf-8").readlines()
    payload = [l for l in lines if not l.startswith("#")]
    assert len(payload) == 1600
