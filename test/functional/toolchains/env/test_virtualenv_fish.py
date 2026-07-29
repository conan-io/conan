import os
import platform
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient

# INFO: Fish is not natively available on Windows, only through Cygwin/WSL
# https://github.com/fish-shell/fish-shell?tab=readme-ov-file#windows
pytestmark = [pytest.mark.tool("fish"),
              pytest.mark.skipif(platform.system() not in ("Darwin", "Linux"),
                                 reason="Fish is only well supported in Linux and Macos")]


@pytest.mark.parametrize("value_with_spaces", [True, False])
def test_buildenv_define_new_vars(value_with_spaces):
    """ Variables declared via ``buildenv_info`` must be exported by the generated ".fish"
    launcher, and correctly restored by its "deactivate_xxx" function, without ever replacing
    the ".sh" launcher used internally by ``self.run()``.
    """
    my_value = "my value" if value_with_spaces else "myvalue"
    cache_folder = os.path.join(temp_folder(), "[sub] folder")
    client = TestClient(cache_folder)
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            def package_info(self):
                self.buildenv_info.define("MYVAR1", "{my_value}")
                self.buildenv_info.prepend_path("PATH", "/fake/prepended/path")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create .")

    client.save_home({"global.conf": "tools.env.virtualenv:fish=True\n"})
    client.save({"conanfile.py": GenConanfile("app", "0.1").with_tool_requires("pkg/0.1")
                                                            .with_generator("VirtualBuildEnv")})
    client.run("install . -s:a os=Linux")

    # The .fish launcher is generated alongside (not instead of) the usual .sh one
    assert os.path.isfile(os.path.join(client.current_folder, "conanbuildenv.sh"))
    buildenv_fish = client.load("conanbuildenv.fish")
    assert f'set -gx MYVAR1 "{my_value}"' in buildenv_fish
    assert 'set -gx PATH "/fake/prepended/path:$PATH"' in buildenv_fish

    build_fish = client.load("conanbuild.fish")
    assert "conanbuildenv.fish" in build_fish

    # NOTE: the fish script must be single-quoted at the shell level, so that the outer sh
    # (which runs this whole command via shell=True) does not expand "$MYVAR1" itself before
    # fish gets a chance to.
    client.run_command("fish -c 'source conanbuild.fish; and echo MYVAR1_IS:$MYVAR1'")
    assert f"MYVAR1_IS:{my_value}" in client.out

    # NOTE: the echo argument must be double-quoted for fish's own sake: an unset variable
    # expands to an empty *list*, so an unquoted "prefix$UNSET_VAR" vanishes entirely instead of
    # becoming "prefix" - quoting forces it to behave like a plain (possibly empty) string.
    client.run_command("fish -c 'source conanbuild.fish; and deactivate_conanbuild; "
                       "and echo \"MYVAR1_AFTER_DEACTIVATE:[$MYVAR1]\"'")
    assert "Restoring environment" in client.out
    assert "MYVAR1_AFTER_DEACTIVATE:[]" in client.out


def test_runenv_buildenv_together():
    """ Build and run envs must generate independent .fish files, both aggregated correctly,
    without mixing each other's variables.
    """
    cache_folder = os.path.join(temp_folder(), "[sub] folder")
    client = TestClient(cache_folder)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            def package_info(self):
                self.buildenv_info.define("FAKE_BUILD_VAR", "build_value")
                self.runenv_info.define("FAKE_RUN_VAR", "run_value")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create .")

    client.save_home({"global.conf": "tools.env.virtualenv:fish=True\n"})
    client.save({"conanfile.py": GenConanfile("app", "0.1").with_requires("pkg/0.1")
                                                            .with_generator("VirtualBuildEnv")
                                                            .with_generator("VirtualRunEnv")})
    client.run("install . -s:a os=Linux")

    buildenv_fish = client.load("conanbuildenv.fish")
    assert 'FAKE_BUILD_VAR' in buildenv_fish
    assert 'FAKE_RUN_VAR' not in buildenv_fish

    runenv_fish = client.load("conanrunenv.fish")
    assert 'FAKE_RUN_VAR' in runenv_fish
    assert 'FAKE_BUILD_VAR' not in runenv_fish

    client.run_command("fish -c 'source conanbuild.fish; and source conanrun.fish; "
                       "and echo VARS:$FAKE_BUILD_VAR,$FAKE_RUN_VAR'")
    assert "VARS:build_value,run_value" in client.out


def test_transitive_tool_requires():
    """ A tool_requires providing a binary and a custom environment variable must be usable
    through the explicit fish launcher via ``self.run(..., env=[...".fish"])``.
    """
    client = TestClient()
    cmd_line = "echo LADY_IS_${LADY}"
    conanfile = str(GenConanfile("tool", "0.1.0")
                    .with_package_file("bin/pkg-echo-tool", cmd_line))
    package_info = """
        os.chmod(os.path.join(self.package_folder, "bin", "pkg-echo-tool"), 0o777)

    def package_info(self):
        self.buildenv_info.define("LADY", "Dulcinea del Toboso")
    """
    conanfile += package_info
    client.save({"tool/conanfile.py": conanfile})
    client.run("create tool")

    conanfile = str(GenConanfile("app", "0.1.0")
                    .with_tool_requires("tool/0.1.0")
                    .with_generator("VirtualBuildEnv"))
    build = """
    def build(self):
        # default self.run(): must still work through the regular .sh launcher
        self.run("pkg-echo-tool", env="conanbuild")
        # explicit opt-in to the fish launcher
        self.run("pkg-echo-tool", env=["conanbuild.fish"])
    """
    conanfile += build
    client.save({"app/conanfile.py": conanfile})
    client.run("create app -c tools.env.virtualenv:fish=True")

    assert client.out.count("LADY_IS_Dulcinea del Toboso") == 2


def test_self_run_default_does_not_use_fish():
    """ The core idea (same as the still-open PR #19649, but for fish): self.run() must keep
    using the underlying shell (.sh) by default, even with the fish conf globally enabled, since
    fish cannot run arbitrary sh-syntax commands. Only an explicit ``env=[...".fish"]`` opts in.
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            def build(self):
                # sh-only syntax ($0 expands to "sh"/"bash", not fish); would break under fish
                self.run("echo SHELL_IS_POSIX:$0")
                self.run("echo FISH_STATUS_BUILTIN_WORKS", env=["conanbuild.fish"])
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . -c tools.env.virtualenv:fish=True")
    assert "SHELL_IS_POSIX" in client.out
    assert "FISH_STATUS_BUILTIN_WORKS" in client.out


def test_no_fish_generated_without_conf():
    """ Without the "tools.env.virtualenv:fish" conf, no .fish file should be generated at all. """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def package_info(self):
                self.buildenv_info.define("MYVAR1", "myvalue")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=pkg --version=0.1")
    client.save({"conanfile.py": GenConanfile("app", "0.1").with_tool_requires("pkg/0.1")
                                                            .with_generator("VirtualBuildEnv")})
    client.run("install . -s:a os=Linux")

    fish_files = [f for f in os.listdir(client.current_folder) if f.endswith(".fish")]
    assert fish_files == []


def test_fish_ignores_deactivation_mode_conf():
    """ fish always deactivates via a function, regardless of "tools.env:deactivation_mode":
    these scripts are only meant for a final consumer to source manually, so keep working
    normally even when that conf, which only affects sh/bat/ps1, is set.
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def package_info(self):
                self.buildenv_info.define("MYVAR1", "myvalue")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=pkg --version=0.1")
    client.save_home({"global.conf": "tools.env.virtualenv:fish=True\n"
                                     "tools.env:deactivation_mode=function\n"})
    client.save({"conanfile.py": GenConanfile("app", "0.1").with_tool_requires("pkg/0.1")
                                                            .with_generator("VirtualBuildEnv")})
    client.run("install . -s:a os=Linux")

    client.run_command("fish -c 'source conanbuild.fish; and echo MYVAR1_IS:$MYVAR1; "
                       "and deactivate_conanbuild; and echo \"MYVAR1_IS:[$MYVAR1]\"'")
    assert "MYVAR1_IS:myvalue" in client.out
    assert "MYVAR1_IS:[]" in client.out
