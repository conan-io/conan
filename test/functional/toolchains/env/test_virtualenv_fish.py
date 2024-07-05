import os
import glob
import platform

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient, load
from conans.util.files import save

# INFO: Fish only supports Cygwin and WSL https://github.com/fish-shell/fish-shell?tab=readme-ov-file#windows
pytestmark = pytest.mark.skipif(platform.system() not in ("Darwin", "Linux"), reason="Fish is well supported only in Linux and MacOS")


@pytest.mark.tool("fish")
@pytest.mark.parametrize("fake_path", ["/path/to/fake/folder", "/path/with space/to/folder"])
@pytest.mark.parametrize("my_var1", ["myvalue", "my value"])
@pytest.mark.parametrize("my_var2", ["varwithspaces", "var with spaces"])
@pytest.mark.parametrize("my_path", ["/path/to/ar", "/path/to space/ar"])
def test_buildenv_define_new_vars(fake_path, my_var1, my_var2, my_path):
    """Test when defining new path and new variable in buildenv_info.

    Variables should be available as environment variables in the buildenv script.
    And, should be deleted when deactivate_conanbuildenv is called.

    Variable with spaces should be wrapped by single quotes when exported.
    """
    cache_folder = os.path.join(temp_folder(), "[sub] folder")
    client = TestClient(cache_folder)
    conanfile = str(GenConanfile("pkg", "0.1"))
    conanfile += f"""

    def package_info(self):
        self.buildenv_info.define_path("MYPATH1", "{my_path}")
        self.buildenv_info.define("MYVAR1", "{my_var1}")
        self.buildenv_info.define("MYVAR2", "{my_var2}")
        self.buildenv_info.prepend_path("PATH", "{fake_path}")
    """
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    save(client.cache.new_config_path, "tools.env.virtualenv:fish=True\n")
    client.save({"conanfile.py": GenConanfile("app", "0.1").with_requires("pkg/0.1")})
    client.run("install . -s:a os=Linux")

    # Only generated fish scripts when virtualenv:fish=True
    for ext in ["*.sh", "*.bat"]:
        not_expected_files = glob.glob(os.path.join(client.current_folder, ext))
        assert not not_expected_files

    # It does not generate conanrun because there is no variables to be exported
    expected_files = sorted(glob.glob(os.path.join(client.current_folder, "*.fish")))
    assert [os.path.join(client.current_folder, "conanbuild.fish"),
            os.path.join(client.current_folder, "conanbuildenv.fish")] == expected_files

    buildenv = load(os.path.join(client.current_folder, "conanbuildenv.fish"))
    assert f'set -gx MYPATH1 "{my_path}"' in buildenv
    assert f'set -gx MYVAR1 "{my_var1}"' in buildenv
    assert f'set -gx MYVAR2 "{my_var2}"' in buildenv
    assert f'set -pgx PATH "{fake_path}"' in buildenv

    wrap_with_quotes = lambda s: f"'{s}'" if ' ' in s else s
    client.run_command('fish -c ". conanbuild.fish; and set; and deactivate_conanbuildenv; and set"')
    # Define variables only once and remove after running deactivate_conanbuildenv
    assert str(client.out).count(f"\nMYPATH1 {wrap_with_quotes(my_path)}\n") == 1
    assert str(client.out).count(f"\nMYVAR1 {wrap_with_quotes(my_var1)}\n") == 1
    assert str(client.out).count(f"\nMYVAR2 {wrap_with_quotes(my_var2)}\n") == 1
    assert str(client.out).count(f"\nPATH '{fake_path}'") == 1
    # Temporary variables to store names should be removed as well
    assert str(client.out).count(f"_PATH {wrap_with_quotes(fake_path)}\n") == 1
    assert str(client.out).count("_del 'MYPATH1'  'MYVAR1'  'MYVAR2'\n") == 1

    # Running conanbuild.fish twice should append variables, but not override them
    client.run_command('fish -c ". conanbuild.fish; . conanbuild.fish; and set"')
    assert str(client.out).count(f"\nMYPATH1 '{my_path}'  '{my_path}'") == 1
    assert str(client.out).count(f"\nMYVAR1 '{my_var1}'  '{my_var1}'") == 1
    assert str(client.out).count(f"\nMYVAR2 '{my_var2}'  '{my_var2}'") == 1
    assert str(client.out).count(f"\nPATH '{fake_path}'  '{fake_path}'") == 1


@pytest.mark.tool("fish")
@pytest.mark.parametrize("fish_value", [True, False])
@pytest.mark.parametrize("path_with_spaces", [True, False])
@pytest.mark.parametrize("value", ["Dulcinea del Toboso", "Dulcinea-Del-Toboso"])
def test_buildenv_transitive_tool_requires(fish_value, path_with_spaces, value):
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


@pytest.mark.tool("fish")
@pytest.mark.parametrize("fake_path", ["/path/to/fake/folder", "/path/with space/to/folder"])
@pytest.mark.parametrize("fake_define", ["FOOBAR", "FOO BAR"])
def test_runenv_buildenv_define_new_vars(fake_path, fake_define):
    """Test when defining new path and new variable using both buildenvinfo and runenvinfo.

    Variables should be available as environment variables in the buildenv and runenv scripts.
    And, should be deleted when deactivate_conanbuildenv and deactivate_conanrunenv are called.
    """
    cache_folder = os.path.join(temp_folder(), "[sub] folder")
    client = TestClient(cache_folder)
    conanfile = str(GenConanfile("pkg", "0.1"))
    conanfile += f"""

    def package_info(self):
        self.buildenv_info.define("FAKE_DEFINE", "{fake_define}")
        self.runenv_info.define_path("FAKE_PATH", "{fake_path}")
    """
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    save(client.cache.new_config_path, "tools.env.virtualenv:fish=True\n")
    client.save({"conanfile.py": GenConanfile("app", "0.1").with_requires("pkg/0.1")})
    client.run("install . -s:a os=Linux")

    # Only generated fish scripts when virtualenv:fish=True
    for ext in ["*.sh", "*.bat"]:
        not_expected_files = glob.glob(os.path.join(client.current_folder, ext))
        assert not not_expected_files

    expected_files = sorted(glob.glob(os.path.join(client.current_folder, "*.fish")))
    assert [os.path.join(client.current_folder, "conanbuild.fish"),
            os.path.join(client.current_folder, "conanbuildenv.fish"),
            os.path.join(client.current_folder, "conanrun.fish"),
            os.path.join(client.current_folder, "conanrunenv.fish")] == expected_files

    # Do not mix buildenv and runenv variables
    script_path = os.path.join(client.current_folder, "conanbuildenv.fish")
    script_content = load(script_path)
    assert f'set -gx FAKE_DEFINE "{fake_define}"' in script_content
    assert 'FAKE_PATH' not in script_content

    script_path = os.path.join(client.current_folder, "conanrunenv.fish")
    script_content = load(script_path)
    assert f'set -pgx FAKE_PATH "{fake_path}"' in script_content
    assert 'FAKE_DEFINE' not in script_content

    # Check if generated wrappers are sourcing the env scripts
    for group in ['build', 'run']:
        script_path = os.path.join(client.current_folder, f"conan{group}.fish")
        script_content = load(script_path)
        assert f'. "{os.path.join(client.current_folder, f"conan{group}env.fish")}"' in script_content

    # Check if the variables are available in the environment
    client.run_command(f'fish -c ". conanbuild.fish; . conanrun.fish; set; deactivate_conanbuildenv; deactivate_conanrunenv; set"')
    wrap_with_quotes = lambda s: f"'{s}'" if ' ' in s else s
    assert f"FAKE_PATH {wrap_with_quotes(fake_path)}" in client.out
    assert f"FAKE_DEFINE {wrap_with_quotes(fake_define)}" in client.out
    # It finds 2 because there is a variable with all values names to be deleted
    assert client.out.count('FAKE_PATH') == 2
    assert client.out.count('FAKE_DEFINE') == 2

    deactivated_content = client.out[client.out.index("Restoring environment"):]
    assert deactivated_content.count('FAKE_PATH') == 0
    assert deactivated_content.count('FAKE_DEFINE') == 0


def test_no_generate_fish():
    """Test when not defining variables and using Fish as virtualenv

       Conan should not generate any .fish file as there is no variables to be exported
    """
    cache_folder = os.path.join(temp_folder(), "[sub] folder")
    client = TestClient(cache_folder)
    conanfile = str(GenConanfile("pkg", "0.1"))
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    save(client.cache.new_config_path, "tools.env.virtualenv:fish=True\n")
    client.save({"conanfile.py": GenConanfile("app", "0.1").with_requires("pkg/0.1")})
    client.run("install . -s:a os=Linux")

    # Do not generate any virtualenv
    for ext in ["*.sh", "*.bat", "*.fish"]:
        not_expected_files = glob.glob(os.path.join(client.current_folder, ext))
        assert not not_expected_files
