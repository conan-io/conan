import os
import threading

from conan.internal.conan_log import ConanLog
from conan.test.utils.test_files import temp_folder


def test_redacts_known_secret_values_everywhere():
    # Redaction is by exact known value (e.g. the parsed args.password/args.token),
    # not by flag name: -p means --password in remote login, but --package-query in
    # list and --provider in audit, so matching by flag name can't tell them apart
    home = temp_folder()
    ConanLog.config(True, home, "conan remote login", ["myremote", "user", "-p", "s3cr3t"],
                    secrets=["s3cr3t"])
    ConanLog().log_message("connecting with password s3cr3t in this message\n")
    ConanLog().log_subprocess_call(b"subprocess echoed s3cr3t back\n", b"")

    content = open(ConanLog.log_path, encoding="utf-8").read()
    assert "s3cr3t" not in content
    assert "# Command: conan remote login myremote user -p ********" in content
    assert "connecting with password ******** in this message" in content
    assert "subprocess echoed ******** back" in content


def test_no_secrets_nothing_is_redacted():
    home = temp_folder()
    ConanLog.config(True, home, "conan list", ["hello/1.0:*", "-p", "os=Windows"])
    ConanLog().log_message("hello/1.0: Nothing to redact here\n")
    content = open(ConanLog.log_path, encoding="utf-8").read()
    assert "# Command: conan list hello/1.0:* -p os=Windows" in content
    assert "Nothing to redact here" in content


def test_config_disabled_by_default():
    ConanLog.config(False, temp_folder(), "conan create", ["."])
    assert ConanLog.log_path is None


def test_config_creates_file_lazily_and_rebuilds_command_line():
    home = temp_folder()
    ConanLog.config(True, home, "conan create", [".", "-cc", "core.log:enabled=True"])
    log_path = ConanLog.log_path
    assert log_path is not None
    assert not os.path.exists(log_path)

    ConanLog().log_message("hello\n")
    assert os.path.exists(log_path)
    content = open(log_path, encoding="utf-8").read()
    assert "# Command: conan create . -cc core.log:enabled=True" in content
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
