import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def _log_files(client):
    log_dir = os.path.join(client.cache_folder, ".log")
    if not os.path.isdir(log_dir):
        return []
    return [os.path.join(log_dir, f) for f in os.listdir(log_dir)]


class TestCommandLog:
    def test_disabled_by_default(self):
        c = TestClient()
        c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
        c.run("create .")
        assert not _log_files(c)

    def test_enabled_via_core_conf(self):
        c = TestClient()
        c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
        c.run("create . -cc core.log:enabled=True")

        logs = _log_files(c)
        assert len(logs) == 1
        content = open(logs[0], encoding="utf-8").read()
        assert "# Command: conan create ." in content
        assert "pkg/1.0: Created package" in content or "pkg/1.0" in content

    def test_enabled_via_global_conf(self):
        c = TestClient()
        c.save_home({"global.conf": "core.log:enabled=True"})
        c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
        c.run("create .")
        assert len(_log_files(c)) == 1

    def test_independent_log_per_command_same_process(self):
        # Regression test: several commands sharing one TestClient (one process) must
        # not end up mixed together in the same log file
        c = TestClient()
        c.save_home({"global.conf": "core.log:enabled=True"})
        c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
        c.run("create .")
        c.run("list pkg/1.0:*")

        logs = _log_files(c)
        assert len(logs) == 2
        create_log = next(f for f in logs if "create" in f)
        list_log = next(f for f in logs if "list" in f)
        create_content = open(create_log, encoding="utf-8").read()
        list_content = open(list_log, encoding="utf-8").read()
        assert "# Command: conan create ." in create_content
        assert "# Command: conan list " in list_content
        assert "list pkg" not in create_content
        assert "Created package" not in list_content

    def test_redacts_password_short_and_long_flags(self):
        c = TestClient(default_server_user=True)
        c.save_home({"global.conf": "core.log:enabled=True"})
        c.run("remote login default admin -p password")

        logs = _log_files(c)
        content = open(logs[0], encoding="utf-8").read()
        assert "password" not in content
        assert "-p ********" in content

    def test_subprocess_output_captured(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "1.0"
                def source(self):
                    self.run("echo hello-from-subprocess")
            """)
        c.save({"conanfile.py": conanfile})
        c.run("create . -cc core.log:enabled=True")

        content = open(_log_files(c)[0], encoding="utf-8").read()
        assert "hello-from-subprocess" in content
