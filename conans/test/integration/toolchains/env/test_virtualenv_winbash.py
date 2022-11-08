import os
import platform
import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.conftest import tools_locations
from conans.test.utils.tools import TestClient
from conans.util.files import save

"""
When we use the VirtualRunEnv and VirtualBuildEnd generators, we take information from the
self.dependencies env_buildinfo and env_runinfo, but to format correctly the environment
variables that are paths to run in a windows bash, we need to look at the consumer conanfile
not the dependency conanfile. This is testing that in the process of aggregating the paths,
these are correct.
"""


@pytest.fixture
def client():
    client = TestClient()
    conanfile = str(GenConanfile())
    conanfile += """

    def package_info(self):
        self.buildenv_info.define_path("AR", "c:/path/to/ar")
        self.buildenv_info.append_path("PATH", "c:/path/to/something")
        self.runenv_info.define_path("RUNTIME_VAR", "c:/path/to/exe")
    """
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=foo --version=1.0")
    save(client.cache.new_config_path, "tools.microsoft.bash:subsystem=cygwin")
    return client


@pytest.mark.xfail(reason="Winbash is broken for multi-profile. Ongoing https://github.com/conan-io/conan/pull/9755")
@pytest.mark.parametrize("win_bash", [True, False, None])
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_virtualenv_deactivated(client, win_bash):
    conanfile = str(GenConanfile().with_settings("os")
                    .with_generator("VirtualBuildEnv").with_generator("VirtualRunEnv")
                    .with_require("foo/1.0"))
    conanfile += """
    {}
    """.format("" if win_bash is None else "win_bash = False"
               if win_bash is False else "win_bash = True")
    client.save({"conanfile.py": conanfile})
    client.run("install . -s:b os=Windows -s:h os=Windows")

    if win_bash:
        # Assert there is no "bat" files generated because the environment can and will be run inside
        # the bash
        assert not os.path.exists(os.path.join(client.current_folder, "conanbuildenv.bat"))
        build_contents = client.load("conanbuildenv.sh")
        assert "/cygdrive/c/path/to/ar" in build_contents
        assert "$PATH:/cygdrive/c/path/to/something" in build_contents
    else:
        assert not os.path.exists(os.path.join(client.current_folder, "conanbuildenv.sh"))
        build_contents = client.load("conanbuildenv.bat")
        assert "c:/path/to/ar" in build_contents
        assert "c:/path/to/something" in build_contents

    assert not os.path.exists(os.path.join(client.current_folder, "conanrunenv.sh"))
    run_contents = client.load("conanrunenv.bat")
    assert "c:/path/to/exe" in run_contents


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_nowinbash(client):
    """ whe the recipe doesn't define win_bash=True 2 things can happen:
    - No need to run in bash, things will run in normal command, with .bat
    - You run directly in a subsytem terminal a recipe that was not aware of that, still the
       files need to follow the subsystem
    """
    conanfile = str(GenConanfile().with_settings("os")
                    .with_generator("VirtualBuildEnv").with_generator("VirtualRunEnv")
                    .with_require("foo/1.0"))

    client.save({"conanfile.py": conanfile})
    client.run("install . -s:b os=Windows -s:h os=Windows")
    assert not os.path.exists(os.path.join(client.current_folder, "conanbuildenv.sh"))
    build_contents = client.load("conanbuildenv.bat")
    assert 'set "AR=c:/path/to/ar"' in build_contents
    assert 'set "PATH=%PATH%;c:/path/to/something"' in build_contents
    assert not os.path.exists(os.path.join(client.current_folder, "conanrunenv.sh"))
    run_contents = client.load("conanrunenv.bat")
    assert 'set "RUNTIME_VAR=c:/path/to/exe"' in run_contents

    # Running it inside a cygwin subsystem
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -s:b os=Windows -s:h os=Windows "
               "-c:h tools.microsoft.bash:active=True")
    assert not os.path.exists(os.path.join(client.current_folder, "conanbuildenv.bat"))
    build_contents = client.load("conanbuildenv.sh")
    assert 'export AR="/cygdrive/c/path/to/ar"' in build_contents
    assert 'export PATH="$PATH:/cygdrive/c/path/to/something"' in build_contents
    assert not os.path.exists(os.path.join(client.current_folder, "conanrunenv.bat"))
    run_contents = client.load("conanrunenv.sh")
    assert 'export RUNTIME_VAR="/cygdrive/c/path/to/exe"' in run_contents

    # Running it inside a msys2 subsystem, test tat it overrides
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -s:b os=Windows -s:h os=Windows "
               "-c tools.microsoft.bash:subsystem=msys2 -c:h tools.microsoft.bash:active=True")
    assert not os.path.exists(os.path.join(client.current_folder, "conanbuildenv.bat"))
    build_contents = client.load("conanbuildenv.sh")
    assert 'export AR="/c/path/to/ar"' in build_contents
    assert 'export PATH="$PATH:/c/path/to/something"' in build_contents
    assert not os.path.exists(os.path.join(client.current_folder, "conanrunenv.bat"))
    run_contents = client.load("conanrunenv.sh")
    assert 'export RUNTIME_VAR="/c/path/to/exe"' in run_contents


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
@pytest.mark.tool("msys2")
def test_conf_inherited_in_test_package():
    client = TestClient()
    bash_path = tools_locations["msys2"]["system"]["path"]["Windows"] + "/bash.exe"
    conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Recipe(ConanFile):
                name="msys2"
                version="1.0"

                def package_info(self):
                    self.conf_info.define("tools.microsoft.bash:subsystem", "msys2")
                    self.conf_info.define("tools.microsoft.bash:path", "{}")
    """.format(bash_path))
    client.save({"conanfile.py": conanfile})
    client.run("create .")

    conanfile = textwrap.dedent("""
                from conan import ConanFile

                class Recipe(ConanFile):
                    name="consumer"
                    version="1.0"
        """)
    test_package = textwrap.dedent("""
                    from conan import ConanFile

                    class Recipe(ConanFile):
                        name="test"
                        version="1.0"
                        win_bash = True

                        def build_requirements(self):
                            self.tool_requires(self.tested_reference_str)
                            self.tool_requires("msys2/1.0")

                        def build(self):
                            self.output.warning(self.conf.get("tools.microsoft.bash:subsystem"))
                            self.run("aclocal --version")

                        def test(self):
                            pass
            """)
    client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_package})
    client.run("create . -s:b os=Windows -s:h os=Windows")
    assert "are needed to run commands in a Windows subsystem" not in client.out
    assert "aclocal (GNU automake)" in client.out
