import os
import platform
import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.tools import save


@pytest.fixture
def client():
    client = TestClient(path_with_spaces=False)
    conanfile = str(GenConanfile("pkg", "0.1"))
    conanfile += """

    def package_info(self):
        self.buildenv_info.define_path("MYPATH1", "c:/path/to/ar")
        self.runenv_info.define("MYVAR1", 'some nice content\" with quotes')
    """
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    save(client.cache.new_config_path, "tools.env.virtualenv:powershell=True\n"
                                       "tools.env.virtualenv:auto_use=True\n")
    return client


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows powershell")
def test_virtualenv(client):
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile

        class ConanFileToolsTest(ConanFile):
            name = "app"
            version = "0.1"
            requires = "pkg/0.1"

            def build(self):
                self.output.info("----------BUILD----------------")
                self.run("set")
                self.output.info("----------RUN----------------")
                self.run("set", env="conanrun")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("install . -s:b os=Windows -s:h os=Windows")

    assert not os.path.exists(os.path.join(client.current_folder, "conanbuildenv.sh"))
    assert not os.path.exists(os.path.join(client.current_folder, "conanbuildenv.bat"))
    assert not os.path.exists(os.path.join(client.current_folder, "conanrunenv.sh"))
    assert not os.path.exists(os.path.join(client.current_folder, "conanrunenv.bat"))
    buildenv = client.load("conanbuildenv.ps1")
    assert '$env:MYPATH1="c:/path/to/ar"' in buildenv
    build = client.load("conanbuild.ps1")
    assert "conanbuildenv.ps1" in build

    run_contents = client.load("conanrunenv.ps1")
    assert '$env:MYVAR1="some nice content`" with quotes"' in run_contents

    client.run("create .")
    assert "MYPATH1=c:/path/to/ar" in client.out
    assert 'MYVAR1=some nice content" with quotes' in client.out
