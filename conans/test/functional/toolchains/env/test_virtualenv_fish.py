import os
import platform

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import save


@pytest.mark.tool("fish")
def test_virtualenv_fish():
    cache_folder = os.path.join(temp_folder(), "[sub] folder")
    client = TestClient(cache_folder)
    conanfile = str(GenConanfile("pkg", "0.1"))
    conanfile += """

    def package_info(self):
        self.buildenv_info.define_path("MYPATH1", "/path/to/ar")
    """
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    save(client.cache.new_config_path, "tools.env.virtualenv:fish=True\n")
    client.save({"conanfile.py": GenConanfile("app", "0.1").with_requires("pkg/0.1")})
    client.run("install . -s:a os=Linux")

    assert not os.path.exists(os.path.join(client.current_folder, "conanbuildenv.sh"))
    assert not os.path.exists(os.path.join(client.current_folder, "conanbuildenv.bat"))
    assert not os.path.exists(os.path.join(client.current_folder, "conanrunenv.sh"))
    assert not os.path.exists(os.path.join(client.current_folder, "conanrunenv.bat"))

    assert os.path.exists(os.path.join(client.current_folder, "conanbuildenv.fish"))
    assert not os.path.exists(os.path.join(client.current_folder, "conanrunenv.fish"))

    with open(os.path.join(client.current_folder, "conanbuildenv.fish"), "r") as f:
        buildenv = f.read()
        assert 'set -gx MYPATH1 "/path/to/ar"' in buildenv

    client.run_command("fish -c 'source conanbuildenv.fish && set'")
    assert 'MYPATH1 /path/to/ar' in client.out

    client.run_command("fish -c 'source conanbuildenv.fish && set && deactivate_conanbuildenv && set'")
    assert str(client.out).count('MYPATH1 /path/to/ar') == 1


@pytest.mark.tool("fish")
# TODO Pass variable with spaces
@pytest.mark.parametrize("fish_value", [True, False])
@pytest.mark.parametrize("path_with_spaces", [True, False])
@pytest.mark.parametrize("value", ["Dulcinea del Toboso", "Dulcinea-Del-Toboso"])
def test_transitive_tool_requires(fish_value, path_with_spaces, value):
    """Generate a tool require package, which provides and binary and a custom environment variable.
    Using fish, the binary should be available in the path, and the environment variable too.
    """
    client = TestClient(path_with_spaces=path_with_spaces)
    save(client.cache.new_config_path, f"tools.env.virtualenv:fish={fish_value}\n")

    # Generate the tool package with pkg-echo-tool binary that prints the value of LADY env var
    cmd_line = "echo ${LADY}" if platform.system() != "Windows" else "echo %LADY%"
    conanfile = str(GenConanfile("tool", "0.1.0")
                    .with_package_file("bin/pkg-echo-tool", cmd_line))
    package_info = f"""
        os.chmod(os.path.join(self.package_folder, "bin", "pkg-echo-tool"), 0o777)

    def package_info(self):
        self.buildenv_info.define("LADY", "{value}")
    """
    conanfile += package_info
    client.save({"tool/conanfile.py": conanfile})
    client.run("create tool")

    assert "tool/0.1.0: package(): Packaged 1 file: pkg-echo-tool" in client.out

    # Generate the app package that uses the tool package. It should be able to run the binary and
    # access the environment variable as well.
    conanfile = str(GenConanfile("app", "0.1.0")
                 .with_tool_requires("tool/0.1.0")
                 .with_generator("VirtualBuildEnv"))
    build = """
    def build(self):
        self.run("pkg-echo-tool", env="conanbuild")
    """
    conanfile += build

    client.save({"app/conanfile.py": conanfile})
    client.run("create app")

    assert value in client.out

    # TODO: Check why is generating when running Conan create:
    # - deactivate_conanbuildenv-release-armv8.fish
    # - conanrunenv-release-armv8.fish
    # No variables listed, only script_folder. Should not generate these files.
