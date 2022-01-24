import os
import platform
import textwrap

import pytest

from conans.model.ref import ConanFileReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TurboTestClient
from conans.util.files import save


@pytest.fixture
def conanfile():
    conanfile = str(GenConanfile().with_import("from conans import tools")
                    .with_import("import os")
                    .with_setting("build_type").with_setting("arch")
                    .with_import("from conan.tools.layout import {ly}")
                    .with_import("from conan.tools.files import AutoPackager"))

    conanfile += """
    def source(self):
        tools.save("myheader.h", "")

    def build(self):
        tools.save("mylib.lib", "")

    def layout(self):
        {ly}(self)

    def package(self):
        AutoPackager(self).run()
    """
    return conanfile


subfolders_arch = {"armv7": "ARM", "armv8": "ARM64", "x86": None, "x86_64": "x64"}


@pytest.mark.parametrize("arch", ["x86_64", "x86", "armv7", "armv8"])
@pytest.mark.parametrize("build_type", ["Debug", "Release"])
@pytest.mark.parametrize("layout_helper_name", ["clion_layout", "vs_layout"])
def test_layout_in_cache(conanfile, layout_helper_name, build_type, arch):
    """The layout in the cache is used too, always relative to the "base" folders that the cache
    requires. But by the default, the "package" is not followed
    """
    client = TurboTestClient()

    ref = ConanFileReference.loads("lib/1.0")
    pref = client.create(ref, args="-s arch={} -s build_type={}".format(arch, build_type),
                         conanfile=conanfile.format(ly=layout_helper_name))
    bf = client.cache.package_layout(pref.ref).build(pref)
    pf = client.cache.package_layout(pref.ref).package(pref)

    build_folder = None
    if layout_helper_name == "clion_layout":
        build_folder = os.path.join(bf, "cmake-build-{}".format(build_type.lower()))
    elif layout_helper_name == "vs_layout":
        if subfolders_arch.get(arch) is not None:
            build_folder = os.path.join(bf, os.path.join(subfolders_arch.get(arch), build_type))
        else:
            build_folder = os.path.join(bf, build_type)

    # Check the build folder
    assert os.path.exists(os.path.join(build_folder, "mylib.lib"))

    # Check the package folder
    assert os.path.exists(os.path.join(pf, "lib/mylib.lib"))
    assert os.path.exists(os.path.join(pf, "include", "myheader.h"))


@pytest.mark.parametrize("arch", ["x86_64", "x86", "armv7", "armv8"])
@pytest.mark.parametrize("build_type", ["Debug", "Release"])
@pytest.mark.parametrize("layout_helper_name", ["clion_layout", "vs_layout"])
def test_layout_with_local_methods(conanfile, layout_helper_name, build_type, arch):
    """The layout in the cache is used too, always relative to the "base" folders that the cache
        requires. But by the default, the "package" is not followed
        """
    client = TestClient()
    client.save({"conanfile.py": conanfile.format(ly=layout_helper_name)})
    client.run("install . lib/1.0@ -s build_type={} -s arch={}".format(build_type, arch))
    client.run("source .")
    # Check the source folder (release)
    assert os.path.exists(os.path.join(client.current_folder, "myheader.h"))
    client.run("build .")
    # Check the build folder (release)
    if layout_helper_name == "clion_layout":
        assert os.path.exists(os.path.join(client.current_folder,
                                           "cmake-build-{}".format(build_type.lower()),
                                           "mylib.lib"))
    elif layout_helper_name == "vs_layout":
        sf_arch = subfolders_arch.get(arch)
        if sf_arch is not None:
            path = os.path.join(client.current_folder, sf_arch, build_type, "mylib.lib")
        else:
            path = os.path.join(client.current_folder, build_type, "mylib.lib")
        assert os.path.exists(path)

    # Check the package
    client.run("package .", assert_error=True)
    assert "The usage of the 'conan package' local method is disabled when using layout()" \
           "" in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Removing msvc compiler")
def test_error_no_msvc():
    # https://github.com/conan-io/conan/issues/9953
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import cmake_layout
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            def layout(self):
                cmake_layout(self)
        """)
    settings_yml = textwrap.dedent("""
        os: [Windows]
        os_build: [Windows]
        arch_build: [x86_64]
        compiler:
            gcc:
                version: ["8"]
        build_type: [Release]
        arch: [x86_64]
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    save(client.cache.settings_path, settings_yml)
    client.run('install . -s os=Windows -s build_type=Release -s arch=x86_64 '
               '-s compiler=gcc -s compiler.version=8')
    assert "Installing" in client.out


def test_error_no_build_type():
    # https://github.com/conan-io/conan/issues/9953
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import cmake_layout
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch"
            def layout(self):
                cmake_layout(self)
        """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run('install .',  assert_error=True)
    assert " 'build_type' setting not defined, it is necessary for cmake_layout()" in client.out
