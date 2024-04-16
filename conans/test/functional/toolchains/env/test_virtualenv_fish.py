import os
import glob
import platform

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import save


@pytest.mark.tool("fish")
def test_define_new_vars():
    """Test when defining new path and new variable in buildenv_info.

    Variables should be available as environment variables in the buildenv script.
    And, should be deleted when deactivate_conanbuildenv is called.
    """
    cache_folder = os.path.join(temp_folder(), "[sub] folder")
    client = TestClient(cache_folder)
    conanfile = str(GenConanfile("pkg", "0.1"))
    conanfile += """

    def package_info(self):
        self.buildenv_info.define_path("MYPATH1", "/path/to/ar")
        self.buildenv_info.define("MYVAR1", "myvalue")
        self.buildenv_info.define("MYVAR2", "var with spaces")
    """
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    save(client.cache.new_config_path, "tools.env.virtualenv:fish=True\n")
    client.save({"conanfile.py": GenConanfile("app", "0.1").with_requires("pkg/0.1")})
    client.run("install . -s:a os=Linux")

    for ext in ["*.sh", "*.bat"]:
        not_expected_files = glob.glob(os.path.join(client.current_folder, ext))
        assert not not_expected_files

    assert os.path.exists(os.path.join(client.current_folder, "conanbuildenv.fish"))
    assert not os.path.exists(os.path.join(client.current_folder, "conanrunenv.fish"))

    with open(os.path.join(client.current_folder, "conanbuildenv.fish"), "r") as f:
        buildenv = f.read()
        assert 'set -gx MYPATH1 "/path/to/ar"' in buildenv
        assert 'set -gx MYVAR1 "myvalue"' in buildenv
        assert 'set -gx MYVAR2 "var with spaces"' in buildenv

    client.run_command("fish -c 'source conanbuildenv.fish && set'")
    assert 'MYPATH1 /path/to/ar' in client.out
    assert 'MYVAR1 myvalue' in client.out
    assert "MYVAR2 'var with spaces'" in client.out

    client.run_command('fish -c ". conanbuildenv.fish && set && deactivate_conanbuildenv && set"')
    assert str(client.out).count('MYPATH1 /path/to/ar') == 1
    assert str(client.out).count('MYVAR1 myvalue') == 1
    assert str(client.out).count("MYVAR2 'var with spaces'") == 1


@pytest.mark.tool("fish")
def test_prepend_path():
    """Test when appending to an existing path in buildenv_info.

    Path should be available as environment variable in the buildenv script, including the new value
    as first element.
    Once deactivate_conanbuildenv is called, the path should be restored as before.
    """
    fake_path = "/path/to/fake/folder"
    cache_folder = os.path.join(temp_folder(), "[sub] folder")
    client = TestClient(cache_folder)
    conanfile = str(GenConanfile("pkg", "0.1"))
    conanfile += f"""

    def package_info(self):
        self.buildenv_info.prepend_path("PATH", "{fake_path}")
    """
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    save(client.cache.new_config_path, "tools.env.virtualenv:fish=True\n")
    client.save({"conanfile.py": GenConanfile("app", "0.1").with_requires("pkg/0.1")})
    client.run("install . -s:a os=Linux")

    for ext in ["*.sh", "*.bat"]:
        not_expected_files = glob.glob(os.path.join(client.current_folder, ext))
        assert not not_expected_files

    assert os.path.exists(os.path.join(client.current_folder, "conanbuildenv.fish"))
    assert not os.path.exists(os.path.join(client.current_folder, "conanrunenv.fish"))

    script_path = os.path.join(client.current_folder, "conanbuildenv.fish")
    with open(script_path, "r") as f:
        buildenv = f.read()
        assert f'set -pgx PATH "{fake_path}"' in buildenv

    client.run_command(f'fish -c ". conanbuildenv.fish; set"')
    assert f'PATH {fake_path}' in client.out

    client.run_command(f'fish -c ". conanbuildenv.fish; deactivate_conanbuildenv; set"')
    assert f'PATH {fake_path}' not in client.out


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
