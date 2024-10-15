import os
import platform
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.fixture
def client():
    client = TestClient()
    conanfile = str(GenConanfile())
    conanfile += """
    def package_info(self):
        self.buildenv_info.define("Foo", "MyVar!")
        self.runenv_info.define("Foo", "MyRunVar!")
    """
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=foo --version=1.0")
    return client


@pytest.mark.parametrize("scope", ["build", "run"])
@pytest.mark.parametrize("default_virtualenv", [True, False, None])
@pytest.mark.parametrize("cli_value", [None, "false"])
def test_virtualenv_deactivated(client, scope, default_virtualenv, cli_value):
    format_str = {True: f"virtual{scope}env = True",
                  False: f"virtual{scope}env = False",
                  None: ""}[default_virtualenv]
    conanfile = textwrap.dedent("""
    from conan import ConanFile

    class ConanFileToolsTest(ConanFile):
        settings = "os"
        {}
        requires = "foo/1.0"
    """).format(format_str)

    client.save({"conanfile.py": conanfile})
    cli_extra = f"--envs-generation={cli_value}" if cli_value is not None else ""
    client.run(f"install . {cli_extra}")
    extension = "bat" if platform.system() == "Windows" else "sh"

    filename = f"conan{scope}env.{extension}"
    filepath = os.path.join(client.current_folder, filename)

    exists_file = os.path.exists(filepath)

    should_exist = cli_value != "false" and (default_virtualenv is None or default_virtualenv)

    if should_exist:
        assert exists_file, f"File {filename} should exist in {os.listdir(client.current_folder)}"
        assert "Foo" in client.load(filepath)
    else:
        assert not exists_file, f"File {filename} should not exist in {os.listdir(client.current_folder)}"


def test_virtualrunenv_not_applied(client):
    """By default the VirtualRunEnv is not added to the list, otherwise when declaring
       generators = "VirtualBuildEnv", "VirtualRunEnv" will be always added"""
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    import platform

    class ConanFileToolsTest(ConanFile):
        settings = "os"
        generators = "VirtualBuildEnv", "VirtualRunEnv"
        requires = "foo/1.0"
    """)

    client.save({"conanfile.py": conanfile})
    client.run("install . ")
    extension = "bat" if platform.system() == "Windows" else "sh"
    exists_file = os.path.exists(os.path.join(client.current_folder,
                                              "conanrun.{}".format(extension)))
    assert exists_file

    global_env = client.load("conanbuild.{}".format(extension))
    assert "conanrunenv" not in global_env


@pytest.mark.parametrize("explicit_declare", [True, False, None])
def test_virtualrunenv_explicit_declare(client, explicit_declare):
    """By default the VirtualRunEnv is not added to the list, otherwise when declaring
       generators = "VirtualBuildEnv", "VirtualRunEnv" will be always added"""
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.env import VirtualRunEnv
    import platform

    class ConanFileToolsTest(ConanFile):
        requires = "foo/1.0"

        def generate(self):
            VirtualRunEnv(self).generate({})

    """).format({True: "scope='build'",
                 False: "scope='run'",
                 None: ""}.get(explicit_declare))

    client.save({"conanfile.py": conanfile})
    client.run("install . ")
    extension = "bat" if platform.system() == "Windows" else "sh"
    exists_file = os.path.exists(os.path.join(client.current_folder,
                                              "conanbuild.{}".format(extension)))
    assert exists_file

    global_env = client.load("conanbuild.{}".format(extension))
    if explicit_declare:
        assert "conanrun" in global_env
    else:
        assert "conanrun" not in global_env
