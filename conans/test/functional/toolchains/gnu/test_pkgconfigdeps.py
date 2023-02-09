import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() == "Windows", reason="Needs pkg-config")
@pytest.mark.tool("pkg_config")
def test_pkg_configdeps_definitions_escape():
    client = TestClient(path_with_spaces=False)
    conanfile = textwrap.dedent(r'''
        from conan import ConanFile
        class HelloLib(ConanFile):
            def package_info(self):
                self.cpp_info.defines.append("USER_CONFIG=\"user_config.h\"")
                self.cpp_info.defines.append('OTHER="other.h"')
                self.cpp_info.cflags.append("flag1=\"my flag1\"")
                self.cpp_info.cxxflags.append('flag2="my flag2"')
        ''')
    client.save({"conanfile.py": conanfile})
    client.run("export . --name=hello --version=1.0")
    client.save({"conanfile.txt": "[requires]\nhello/1.0\n"}, clean_first=True)
    client.run("install . --build=missing -g PkgConfigDeps")
    client.run_command("PKG_CONFIG_PATH=$(pwd) pkg-config --cflags hello")
    assert r'flag2=\"my flag2\" flag1=\"my flag1\" ' \
           r'-DUSER_CONFIG=\"user_config.h\" -DOTHER=\"other.h\"' in client.out


@pytest.mark.tool("cmake")
def test_pkgconfigdeps_with_test_requires():
    """
    PkgConfigDeps has to create any test requires declared on the recipe.

    Related issue: https://github.com/conan-io/conan/issues/11376
    """
    client = TestClient()
    with client.chdir("app"):
        client.run("new cmake_lib -d name=app -d version=1.0")
        client.run("create . -tf=\"\"")
    with client.chdir("test"):
        client.run("new cmake_lib -d name=test -d version=1.0")
        client.run("create . -tf=\"\"")
    # Create library having build and test requires
    conanfile = textwrap.dedent(r'''
        from conan import ConanFile
        class HelloLib(ConanFile):
            def build_requirements(self):
                self.test_requires('app/1.0')
                self.test_requires('test/1.0')
        ''')
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -g PkgConfigDeps")
    assert "Description: Conan package: test" in client.load("test.pc")
    assert "Description: Conan package: app" in client.load("app.pc")
