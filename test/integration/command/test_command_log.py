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

    def test_enabled(self):
        # core.log:enabled is only honored from global.conf: it is read before any
        # argument is parsed, so a `-cc core.log:enabled=True` override isn't seen yet
        c = TestClient()
        c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
        c.save_home({"global.conf": "core.log:enabled=True"})
        c.run("create .")

        logs = _log_files(c)
        assert len(logs) == 1
        content = open(logs[0], encoding="utf-8").read()
        assert "# Command: conan create ." in content
        assert "pkg/1.0" in content

    def test_core_conf_override_not_honored(self):
        # Trade-off of activating once, up front, in Cli.run(): core.log:enabled is
        # read before any argument is parsed, so -cc can't be seen yet at that point
        c = TestClient()
        c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
        c.run("create . -cc core.log:enabled=True")
        assert not _log_files(c)

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

    def test_nested_command_shares_the_outer_log(self):
        # Regression test: a command calling conan_api.command.run() internally used to
        # reconfigure the process-wide log context, so anything the outer command logged
        # after the nested call ended up in the nested command's own log file instead.
        # Everything happening in the same process, nested or not, belongs in one file
        c = TestClient()
        c.save_home({
            "global.conf": "core.log:enabled=True",
            "extensions/commands/cmd_mybuild.py": textwrap.dedent("""
                from conan.api.output import ConanOutput
                from conan.cli.command import conan_command

                @conan_command(group="Custom commands")
                def mybuild(conan_api, parser, *args):
                    \"\"\"mybuild\"\"\"
                    parser.parse_args(args[0])
                    ConanOutput().info("mybuild: before nested command")
                    conan_api.command.run(["profile", "detect", "--force"])
                    ConanOutput().info("mybuild: after nested command")
                """),
        })
        c.run("mybuild")

        logs = _log_files(c)
        assert len(logs) == 1
        content = open(logs[0], encoding="utf-8").read()
        assert "# Command: conan mybuild" in content
        assert "mybuild: before nested command" in content
        assert "Detected profile" in content
        assert "mybuild: after nested command" in content

    def test_redacts_password_by_value_end_to_end(self):
        c = TestClient(default_server_user=True)
        c.save_home({"global.conf": "core.log:enabled=True"})
        c.run("remote login default admin -p password")

        content = open(_log_files(c)[0], encoding="utf-8").read()
        assert "-p ********" in content
        assert content.count("password") == 0

    def test_p_flag_not_confused_with_password_in_other_commands(self):
        # Regression test: -p means --password in remote login, but --package-query in
        # list; redacting by flag name used to mask this value as a false positive
        c = TestClient()
        c.save_home({"global.conf": "core.log:enabled=True"})
        c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
        c.run("create .")
        c.run("list pkg/1.0:* -p os=Windows")

        list_log = next(f for f in _log_files(c) if "list" in f)
        content = open(list_log, encoding="utf-8").read()
        assert "# Command: conan list pkg/1.0:* -p os=Windows" in content

    def test_run_quiet_does_not_crash(self):
        # Regression test: self.run(cmd, quiet=True) maps stdout/stderr to
        # subprocess.DEVNULL, which used to crash trying to write() to it
        c = TestClient()
        c.save_home({"global.conf": "core.log:enabled=True"})
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "1.0"
                def build(self):
                    self.run("echo quiet-output", quiet=True)
                    self.run("echo loud-output")
            """)
        c.save({"conanfile.py": conanfile})
        c.run("create .")

        content = open(_log_files(c)[0], encoding="utf-8").read()
        assert "loud-output" in content
        assert "quiet-output" not in content

    def test_subprocess_output_captured(self):
        c = TestClient()
        c.save_home({"global.conf": "core.log:enabled=True"})
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "1.0"
                def source(self):
                    self.run("echo hello-from-subprocess")
            """)
        c.save({"conanfile.py": conanfile})
        c.run("create .")

        content = open(_log_files(c)[0], encoding="utf-8").read()
        assert "hello-from-subprocess" in content
