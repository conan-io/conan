import os
import platform
import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.tools import save


@pytest.fixture
def client():
    client = TestClient()
    conanfile = str(GenConanfile())
    conanfile += """
    def package_info(self):
        self.buildenv_info.define("Foo", "MyVar!")
    """
    client.save({"conanfile.py": conanfile})
    client.run("create . foo/1.0@")
    save(client.cache.new_config_path, "tools.env.virtualenv:auto_use=True")
    return client


@pytest.mark.parametrize("default_virtualenv", [True, False, None])
def test_virtualenv_deactivated(client, default_virtualenv):
    format_str = {True: "virtualenv = True",
                  False: "virtualenv = False",
                  None: ""}[default_virtualenv]
    conanfile = textwrap.dedent("""
    from conans import ConanFile
    from conans.client.runner import ConanRunner
    import platform

    class ConanFileToolsTest(ConanFile):
        {}
        requires = "foo/1.0"
    """).format(format_str)

    client.save({"conanfile.py": conanfile})
    client.run("install . ")
    extension = "bat" if platform.system() == "Windows" else "sh"
    exists_file = os.path.exists(os.path.join(client.current_folder, "conanbuildenv.{}".format(extension)))
    if default_virtualenv is True or default_virtualenv is None:
        assert exists_file
    elif default_virtualenv is False:
        assert not exists_file
