import platform
import sys
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() == "Windows", reason="Needs pkg-config")
@pytest.mark.tool("pkg_config")
def test_pkgconfigdeps_definitions_escape():
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


@pytest.mark.skipif(sys.version_info.minor < 7, reason="Meson 1.1.x version needs Python >= 3.7")
@pytest.mark.skipif(platform.system() != "Windows", reason="It makes sense only for Windows")
@pytest.mark.tool("meson")  # https://github.com/mesonbuild/meson/pull/11649 is part of Meson 1.1.0
@pytest.mark.tool("pkg_config")
def test_pkgconfigdeps_bindir_and_meson():
    """
    This test checks that the field bindir introduced by PkgConfigDeps is useful for Windows
    OS and shared=True where all the DLL's files are located by default there.

    Basically, Meson (version >= 1.1.0) reads from the *.pc files the bindir variable if exists, and
    uses that variable to link with if SHARED libraries.

    Issue: https://github.com/conan-io/conan/issues/13532
    """
    client = TestClient()
    client.run("new meson_lib -d name=hello -d version=1.0")
    client.run("create . -tf \"\" -o *:shared=True")
    test_meson_build = textwrap.dedent("""
    project('Testhello', 'cpp')
    hello = dependency('hello', version : '>=1.0')
    example = executable('example', 'src/example.cpp', dependencies: hello)
    test('./src/example', example)
    """)
    test_conanfile = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.build import can_run
    from conan.tools.meson import Meson
    from conan.tools.layout import basic_layout

    class helloTestConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        generators = "PkgConfigDeps", "MesonToolchain"
        options = {"shared": [True, False], "fPIC": [True, False]}
        default_options = {"shared": True, "fPIC": True}

        def requirements(self):
            self.requires("hello/1.0")

        def build(self):
            meson = Meson(self)
            meson.configure()
            meson.build()

        def layout(self):
            basic_layout(self)
    """)
    client.save({
        "test_package/conanfile.py": test_conanfile,
        "test_package/meson.build": test_meson_build
    })
    client.run("build test_package/conanfile.py -o *:shared=True")
    # Important: Only Meson >= 1.1.0 brings this capability
    # Executing directly "meson test" fails if the bindir field does not exist
    client.run_command("meson test -C test_package/build-release")
    assert "1/1 ./src/example OK"


@pytest.mark.tool("meson")
@pytest.mark.tool("pkg_config")
def test_pkgconfigdeps_pc_name_conflict():
    """
    This test checks that a pc file provided by component is not overwritten by
    conan with pc file named after the package if the names collide.
    Cases insensitive filesystems have to be taken into account.
    """
    client = TestClient()
    client.run("new meson_lib -d name=hello -d version=1.0")
    client.run("create . -tf=\"\"")
    conanfile = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.meson import MesonToolchain, Meson
    from conan.tools.layout import basic_layout
    from conan.tools.files import copy

    class helloConan(ConanFile):
        name = "hello"
        version = "1.0"
        package_type = "library"

        # Binary configuration
        settings = "os", "compiler", "build_type", "arch"
        options = {"shared": [True, False], "fPIC": [True, False]}
        default_options = {"shared": False, "fPIC": True}

        # Sources are located in the same place as this recipe, copy them to the recipe
        exports_sources = "meson.build", "src/*"

        def config_options(self):
            if self.settings.os == "Windows":
                self.options.rm_safe("fPIC")

        def configure(self):
            if self.options.shared:
                self.options.rm_safe("fPIC")

        def layout(self):
            basic_layout(self)

        def generate(self):
            tc = MesonToolchain(self)
            tc.generate()

        def build(self):
            meson = Meson(self)
            meson.configure()
            meson.build()

        def package(self):
            meson = Meson(self)
            meson.install()

        def package_info(self):
            self.cpp_info.components["component"].set_property("pkg_config_name", "Hello")
            self.cpp_info.components["component"].libs = ["hello"]
    """)
    client.save({"conanfile.py": conanfile})
    client.run("build test_package/conanfile.py")
    client.run_command("meson test -C test_package/build-release")
    assert "1/1 ./src/example OK"
