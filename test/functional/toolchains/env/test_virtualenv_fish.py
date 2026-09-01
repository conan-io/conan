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
    """ A tool_requires providing a binary and a custom environment variable must still work
    normally through the regular .sh launcher while the fish conf is enabled.
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
        self.run("pkg-echo-tool", env="conanbuild")
    """
    conanfile += build
    client.save({"app/conanfile.py": conanfile})
    client.run("create app -c tools.env.virtualenv:fish=True")

    assert "LADY_IS_Dulcinea del Toboso" in client.out


def test_self_run_never_uses_fish():
    """ The core idea (same as the still-open PR #19649, but for fish): self.run() always runs in
    the regular shell, even with the fish conf enabled, because fish cannot run arbitrary
    sh-syntax commands. Asking for the .fish launcher explicitly does not opt in either.

    Uses a command whose *output* differs per shell, so this cannot pass vacuously: ``$version``
    is a fish-only variable, and ``$$`` is a POSIX-only one, so the printed line identifies which
    shell really ran it.
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            generators = "VirtualBuildEnv"
            def build(self):
                # The launcher really is there, so what follows is a deliberate choice and not
                # just a fallback because the file was missing
                assert os.path.exists(os.path.join(self.generators_folder, "conanbuild.fish"))
                # In fish "$version" holds its version string; in a POSIX shell it is empty. So a
                # line reading "FISHVER=[]" proves a POSIX shell ran this, not fish.
                self.run('echo "MARK1 FISHVER=[$version]"')
                self.run('echo "MARK2 FISHVER=[$version]"', env=["conanbuild.fish"])
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . -c tools.env.virtualenv:fish=True")
    # Both the default and the explicit-.fish call ran in a POSIX shell, where $version is empty
    assert "MARK1 FISHVER=[]" in client.out
    assert "MARK2 FISHVER=[]" in client.out


HOSTILE_VALUES = {
    # A "$" not followed by a valid fish variable name is a *parse error*, not just an expansion
    "MYDOLLARBRACE": "--libdir=${prefix}/lib",
    "MYTRAILDOLLAR": "price is 5$",
    # A "$" that does look like a variable would silently expand to nothing
    "MYRPATH": "-Wl,-rpath,$ORIGIN/../lib",
    "MYCMDSUB": "$(whoami)",
    "MYQUOTES": 'say "hi"',
    "MYBACKSLASH": r"C:\path\to",
}


def test_hostile_values_are_escaped():
    """ Inside a fish double-quoted string ``\\``, ``"`` and ``$`` are all special. Escaping only
    ``"`` is not enough: a ``$`` not followed by a valid variable name is a parse error that aborts
    the *whole* sourced file, so every other variable in it silently goes missing too.
    """
    client = TestClient()
    conanfile = ("from conan import ConanFile\n"
                 "class Pkg(ConanFile):\n"
                 "    name = 'pkg'\n"
                 "    version = '0.1'\n"
                 "    def package_info(self):\n"
                 + "".join(f"        self.buildenv_info.define({k!r}, {v!r})\n"
                           for k, v in HOSTILE_VALUES.items()))
    client.save({"conanfile.py": conanfile})
    client.run("create .")

    client.save_home({"global.conf": "tools.env.virtualenv:fish=True\n"})
    client.save({"conanfile.py": GenConanfile("app", "0.1").with_tool_requires("pkg/0.1")
                                                           .with_generator("VirtualBuildEnv")})
    client.run("install . -s:a os=Linux")

    # Only double quotes are used below, so the whole thing survives the outer sh single quotes
    dump = "; ".join(f'echo "{k}=[${k}]"' for k in HOSTILE_VALUES)
    client.run_command(f"fish -c 'source conanbuild.fish; {dump}'")
    for name, value in HOSTILE_VALUES.items():
        assert f"{name}=[{value}]" in client.out


def test_aggregated_fish_sources_every_launcher():
    """ ``set -e`` of a non-existing variable returns 4 in fish (POSIX ``unset`` returns 0), so
    chaining the aggregated launchers with ``&&`` meant that a launcher whose last statement was
    an unset aborted the chain, silently skipping every later launcher.
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            def package_info(self):
                self.buildenv_info.define("MYVAR1", "myvalue")
                self.buildenv_info.unset("SOMEUNSETVAR")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create .")

    client.save_home({"global.conf": "tools.env.virtualenv:fish=True\n"})
    # A second registered launcher, so the aggregated conanbuild.fish sources more than one file
    consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save
        class App(ConanFile):
            name = "app"
            version = "0.1"
            tool_requires = "pkg/0.1"
            generators = "VirtualBuildEnv"
            def generate(self):
                save(self, "myextra.fish", 'set -gx EXTRA_VAR "extravalue"\\n')
                self.env_scripts.setdefault("build", []).append("myextra.fish")
        """)
    client.save({"conanfile.py": consumer})
    client.run("install . -s:a os=Linux")

    # The unset is guarded, so sourcing the launcher leaves a 0 status
    assert "if set -q SOMEUNSETVAR" in client.load("conanbuildenv.fish")
    assert " && " not in client.load("conanbuild.fish")

    client.run_command('fish -c \'source conanbuild.fish; echo "GOT:$MYVAR1,$EXTRA_VAR"\'')
    assert "GOT:myvalue,extravalue" in client.out

    # The documented "source it, then run something" idiom must not be broken by the unset either
    client.run_command("fish -c 'source conanbuildenv.fish && echo CHAIN_OK'")
    assert "CHAIN_OK" in client.out


def test_empty_variable_does_not_leave_stray_separator():
    """ A variable that exists but is empty must be treated like an unset one, otherwise the
    append/prepend leaves a dangling separator -- and an empty PATH element means "current
    directory". ``save_sh`` gets this right with ``${VAR:+sep$VAR}``; fish needs ``test -n``,
    because ``set -q`` is also true for a variable that is set but empty.
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            def package_info(self):
                self.buildenv_info.append_path("MYFISHPATH", "/newp")
                self.buildenv_info.append("MYFISHFLAGS", "-added")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create .")

    client.save_home({"global.conf": "tools.env.virtualenv:fish=True\n"})
    client.save({"conanfile.py": GenConanfile("app", "0.1").with_tool_requires("pkg/0.1")
                                                           .with_generator("VirtualBuildEnv")})
    client.run("install . -s:a os=Linux")

    for prelude in ("env MYFISHPATH= MYFISHFLAGS=",  # set but empty
                    "env -u MYFISHPATH -u MYFISHFLAGS"):  # not set at all
        client.run_command(f'{prelude} fish -c '
                           '\'source conanbuild.fish; '
                           'echo "P=[$MYFISHPATH] F=[$MYFISHFLAGS]"\'')
        assert "P=[/newp] F=[-added]" in client.out


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
