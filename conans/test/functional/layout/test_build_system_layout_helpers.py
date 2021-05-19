import os

import pytest

from conans.model.ref import ConanFileReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TurboTestClient


@pytest.fixture
def conanfile():
    conanfile = str(GenConanfile().with_import("from conans import tools")
                    .with_import("import os")
                    .with_setting("build_type").with_setting("arch")
                    .with_import("from conan.tools.layout import {ly}, LayoutPackager"))

    conanfile += """
    def source(self):
        tools.save("myheader.h", "")

    def build(self):
        tools.save("mylib.lib", "")

    def layout(self):
        {ly}(self)
        self.folders.package = "my_package"

    def package(self):
        LayoutPackager(self).package()
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
    bf = client.cache.pkg_layout(pref).build()
    pf = client.cache.pkg_layout(pref).package()

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
    client.run("build . --name=lib --version=1.0 -s build_type={} -s arch={}".format(build_type,
                                                                                     arch))
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
    # client.run("package .")
    # assert os.path.exists(os.path.join(client.current_folder, "my_package", "lib", "mylib.lib"))

