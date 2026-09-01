import os
import threading

from conan.internal.conan_log import ConanLog
from conan.test.utils.test_files import temp_folder


class _FakeConfig:
    def __init__(self, enabled):
        self._enabled = enabled

    def get(self, name, default=False, check_type=bool):
        return self._enabled


class _FakeConanApi:
    def __init__(self, home, enabled=True):
        self.home_folder = home
        self.config = _FakeConfig(enabled)


def test_redacts_known_secret_values_everywhere():
    # Redaction is by exact known value (e.g. the parsed args.password/args.token),
    # not by flag name: -p means --password in remote login, but --package-query in
    # list and --provider in audit, so matching by flag name can't tell them apart
    home = temp_folder()
    with ConanLog.activate(_FakeConanApi(home), ["remote", "login"]):
        ConanLog.set_context("conan remote login", ["myremote", "user", "-p", "s3cr3t"],
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
    with ConanLog.activate(_FakeConanApi(home), ["list"]):
        ConanLog.set_context("conan list", ["hello/1.0:*", "-p", "os=Windows"], None)
        ConanLog().log_message("hello/1.0: Nothing to redact here\n")
        content = open(ConanLog.log_path, encoding="utf-8").read()

    assert "# Command: conan list hello/1.0:* -p os=Windows" in content
    assert "Nothing to redact here" in content


def test_activate_disabled_by_default():
    with ConanLog.activate(_FakeConanApi(temp_folder(), enabled=False), ["create"]):
        assert ConanLog.log_path is None


def test_activate_creates_no_file_until_set_context_commits_header():
    # activate() only computes log_path; the file itself, and the header, are only
    # written once set_context() knows the command line (needed so a nested command's
    # own set_context() can't steal the header, see the test below)
    home = temp_folder()
    with ConanLog.activate(_FakeConanApi(home), ["create", ".", "-cc", "core.log:enabled=True"]):
        log_path = ConanLog.log_path
        assert log_path is not None
        assert not os.path.exists(log_path)

        ConanLog.set_context("conan create", [".", "-cc", "core.log:enabled=True"], None)
        assert os.path.exists(log_path)
        content = open(log_path, encoding="utf-8").read()

    assert "# Command: conan create . -cc core.log:enabled=True" in content


def test_nested_set_context_does_not_steal_header_but_secrets_merge():
    # Regression test: a command calling conan_api.command.run() internally, before
    # printing anything itself, used to let the nested command's own set_context()
    # overwrite the header. The header must stay the outer command's, but the nested
    # command's secrets must still be redacted for the rest of the log
    home = temp_folder()
    with ConanLog.activate(_FakeConanApi(home), ["mybuild"]):
        ConanLog.set_context("conan mybuild", [], ["outer-secret"])
        ConanLog.set_context("conan profile detect", ["--force"], ["inner-secret"])
        ConanLog().log_message("outer-secret and inner-secret shown here\n")
        content = open(ConanLog.log_path, encoding="utf-8").read()

    assert "# Command: conan mybuild" in content
    assert "outer-secret" not in content
    assert "inner-secret" not in content


def test_activate_is_independent_per_command():
    home = temp_folder()
    with ConanLog.activate(_FakeConanApi(home), ["profile", "detect"]):
        ConanLog.set_context("conan profile", ["detect"], None)
        ConanLog().log_message("first command\n")
        first_path = ConanLog.log_path

    with ConanLog.activate(_FakeConanApi(home), ["install", "."]):
        ConanLog.set_context("conan install", ["."], None)
        second_path = ConanLog.log_path
        assert second_path != first_path
        ConanLog().log_message("second command\n")

    assert "first command" in open(first_path, encoding="utf-8").read()
    assert "second command" in open(second_path, encoding="utf-8").read()
    assert "second command" not in open(first_path, encoding="utf-8").read()


def test_concurrent_writes_are_not_lost():
    home = temp_folder()
    with ConanLog.activate(_FakeConanApi(home), ["create", "."]):
        ConanLog.set_context("conan create", ["."], None)

        def worker(n):
            for i in range(200):
                ConanLog().log_message(f"thread{n}-line{i}\n")

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        log_path = ConanLog.log_path

    lines = open(log_path, encoding="utf-8").readlines()
    payload = [l for l in lines if not l.startswith("#")]
    assert len(payload) == 1600
