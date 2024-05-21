import json
import platform
import textwrap
from unittest.mock import patch, MagicMock

import pytest

from conan.tools.system.package_manager import _SystemPackageManagerTool
from conan.test.utils.tools import TestClient


@pytest.mark.tool("apt_get")
@pytest.mark.skipif(platform.system() != "Linux", reason="Requires apt")
def test_apt_check():
    client = TestClient()
    client.save({"conanfile.py": textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.system.package_manager import Apt

        class MyPkg(ConanFile):
            settings = "arch", "os"
            def system_requirements(self):
                apt = Apt(self)
                not_installed = apt.check(["non-existing1", "non-existing2"])
                print("missing:", not_installed)
        """)})
    client.run("create . --name=test --version=1.0 -s:b arch=armv8 -s:h arch=x86")
    assert "dpkg-query: no packages found matching non-existing1:i386" in client.out
    assert "dpkg-query: no packages found matching non-existing2:i386" in client.out
    assert "missing: ['non-existing1', 'non-existing2']" in client.out


@pytest.mark.tool("apt_get")
@pytest.mark.skipif(platform.system() != "Linux", reason="Requires apt")
def test_apt_install_substitutes():
    client = TestClient()
    conanfile_py = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.system.package_manager import Apt
        class MyPkg(ConanFile):
            settings = "arch", "os"
            def system_requirements(self):
                # FIXME this is needed because the ci-functional apt-get update fails
                try:
                    self.run("sudo apt-get update")
                except Exception:
                    pass
                apt = Apt(self)
                {}
        """)

    installs = 'apt.install_substitutes(["non-existing1", "non-existing2"], ["non-existing3", "non-existing4"])'
    client.save({"conanfile.py": conanfile_py.format(installs)})
    client.run("create . --name=test --version=1.0 -c tools.system.package_manager:mode=install "
               "-c tools.system.package_manager:sudo=True", assert_error=True)
    assert "dpkg-query: no packages found matching non-existing1" in client.out
    assert "dpkg-query: no packages found matching non-existing2" in client.out
    assert "dpkg-query: no packages found matching non-existing3" in client.out
    assert "dpkg-query: no packages found matching non-existing4" in client.out
    assert "None of the installs for the package substitutes succeeded." in client.out

    client.run_command("sudo apt remove nano -yy")
    installs = 'apt.install_substitutes(["non-existing1", "non-existing2"], ["nano"], ["non-existing3"])'
    client.save({"conanfile.py": conanfile_py.format(installs)})
    client.run("create . --name=test --version=1.0 -c tools.system.package_manager:mode=install "
               "-c tools.system.package_manager:sudo=True")
    assert "1 newly installed" in client.out


@pytest.mark.tool("apt_get")
@pytest.mark.skipif(platform.system() != "Linux", reason="Requires apt")
def test_build_require():
    client = TestClient()
    client.save({"tool_require.py": textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.system.package_manager import Apt

        class MyPkg(ConanFile):
            settings = "arch", "os"
            def system_requirements(self):
                apt = Apt(self)
                not_installed = apt.check(["non-existing1", "non-existing2"])
                print("missing:", not_installed)
        """)})
    client.run("export tool_require.py --name=tool_require --version=1.0")
    client.save({"consumer.py": textwrap.dedent("""
        from conan import ConanFile
        class consumer(ConanFile):
            settings = "arch", "os"
            tool_requires = "tool_require/1.0"
        """)})
    client.run("create consumer.py --name=consumer --version=1.0 "
               "-s:b arch=armv8 -s:h arch=x86 --build=missing")
    assert "dpkg-query: no packages found matching non-existing1" in client.out
    assert "dpkg-query: no packages found matching non-existing2" in client.out
    assert "missing: ['non-existing1', 'non-existing2']" in client.out


@pytest.mark.tool("brew")
@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires brew")
def test_brew_check():
    client = TestClient()
    client.save({"conanfile.py": textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.system.package_manager import Brew

        class MyPkg(ConanFile):
            settings = "arch"
            def system_requirements(self):
                brew = Brew(self)
                not_installed = brew.check(["non-existing1", "non-existing2"])
                print("missing:", not_installed)
        """)})
    client.run("create . --name=test --version=1.0")
    assert "missing: ['non-existing1', 'non-existing2']" in client.out


@pytest.mark.tool("brew")
@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires brew")
@pytest.mark.skip(reason="brew update takes a lot of time")
def test_brew_install_check_mode():
    client = TestClient()
    client.save({"conanfile.py": textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.system.package_manager import Brew

        class MyPkg(ConanFile):
            settings = "arch"
            def system_requirements(self):
                brew = Brew(self)
                brew.install(["non-existing1", "non-existing2"])
        """)})
    client.run("create . test/1.0@", assert_error=True)
    assert "System requirements: 'non-existing1, non-existing2' are missing but " \
           "can't install because tools.system.package_manager:mode is 'check'" in client.out


@pytest.mark.tool("brew")
@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires brew")
@pytest.mark.skip(reason="brew update takes a lot of time")
def test_brew_install_install_mode():
    client = TestClient()
    client.save({"conanfile.py": textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.system.package_manager import Brew

        class MyPkg(ConanFile):
            settings = "arch"
            def system_requirements(self):
                brew = Brew(self)
                brew.install(["non-existing1", "non-existing2"])
        """)})
    client.run("create . test/1.0@ -c tools.system.package_manager:mode=install", assert_error=True)
    assert "Error: No formulae found in taps." in client.out


def test_collect_system_requirements():
    """ we can know the system_requires for every package because they are part of the graph,
    this naturally execute at ``install``, but we can also prove that with ``graph info`` we can
    for it to with the righ ``mode=collect`` mode.
    """
    client = TestClient()
    client.save({"conanfile.py": textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.system.package_manager import Brew, Apt

        class MyPkg(ConanFile):
            settings = "arch"
            def system_requirements(self):
                brew = Brew(self)
                brew.install(["brew1", "brew2"])
                apt = Apt(self)
                apt.install(["pkg1", "pkg2"])
        """)})

    with patch.object(_SystemPackageManagerTool, '_conanfile_run', MagicMock(return_value=False)):
        client.run("install . -c tools.system.package_manager:tool=apt-get --format=json",
                   redirect_stdout="graph.json")
    graph = json.loads(client.load("graph.json"))
    assert {"apt-get": {"install": ["pkg1", "pkg2"], "missing": []}} == \
           graph["graph"]["nodes"]["0"]["system_requires"]

    # plain report, do not check
    client.run("graph info . -c tools.system.package_manager:tool=apt-get "
               "-c tools.system.package_manager:mode=report --format=json",
               redirect_stdout="graph2.json")
    graph2 = json.loads(client.load("graph2.json"))
    # TODO: Unify format of ``graph info`` and ``install``
    assert {"apt-get": {"install": ["pkg1", "pkg2"]}} == \
           graph2["graph"]["nodes"]["0"]["system_requires"]

    # Check report-installed
    with patch.object(_SystemPackageManagerTool, '_conanfile_run', MagicMock(return_value=True)):
        client.run("graph info . -c tools.system.package_manager:tool=apt-get "
                   "-c tools.system.package_manager:mode=report-installed --format=json",
                   redirect_stdout="graph2.json")
        graph2 = json.loads(client.load("graph2.json"))
        assert {"apt-get": {"install": ["pkg1", "pkg2"],
                            'missing': ['pkg1', 'pkg2']}} == graph2["graph"]["nodes"]["0"]["system_requires"]

    # Default "check" will fail, as dpkg-query not installed
    client.run("graph info . -c tools.system.package_manager:tool=apt-get "
               "-c tools.system.package_manager:mode=check", assert_error=True)
    assert "ERROR: conanfile.py: Error in system_requirements() method, line 11" in client.out
