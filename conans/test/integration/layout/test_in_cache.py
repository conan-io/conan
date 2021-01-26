import os
import pytest

from conans import load
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


@pytest.fixture
def conanfile():
    conan_file = str(GenConanfile().with_import("from conans import tools").with_import("import os").
                     with_require("base/1.0"))

    # FIXME: The configure is not valid to change the layout, we need the settings and options
    #        ready
    conan_file += """
    no_copy_sources = True

    def configure(self):
        self.layout.source.folder = "my_sources"
        self.layout.build.folder = "my_build"

    def source(self):
        self.output.warn("Source folder: {}".format(self.source_folder))
        tools.save("source.h", "foo")

    def build(self):
        self.output.warn("Build folder: {}".format(self.build_folder))
        tools.save("build.lib", "bar")

    def package(self):
        self.output.warn("Package folder: {}".format(self.package_folder))
        tools.save(os.path.join(self.package_folder, "LICENSE"), "bar")
        self.copy("*.h", dst="include")
        self.copy("*.lib", dst="lib")

    def package_info(self):
        # This will be easier when the layout declares also the includedirs etc
        self.cpp_info.includedirs = [os.path.join(self.package_folder, "include")]
        self.cpp_info.libdirs = [os.path.join(self.package_folder, "lib")]
    """
    return conan_file


def test_cache_in_layout(conanfile):
    """The layout in the cache is used too, always relative to the "base" folders that the cache
    requires. But by the default, the "package" is not followed
    """
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . base/1.0@")

    client.save({"conanfile.py": conanfile})
    ref = ConanFileReference.loads("lib/1.0@")
    pref = PackageReference(ref, "58083437fe22ef1faaa0ab4bb21d0a95bf28ae3d")
    sf = client.cache.package_layout(ref).source()
    bf = client.cache.package_layout(ref).build(pref)
    pf = client.cache.package_layout(ref).package(pref)

    source_folder = os.path.join(sf, "my_sources")
    build_folder = os.path.join(bf, "my_build")

    client.run("create . lib/1.0@")
    # Check folders match with the declared by the layout
    assert "Source folder: {}".format(source_folder) in client.out
    assert "Build folder: {}".format(build_folder) in client.out
    # Check the source folder
    assert os.path.exists(os.path.join(source_folder, "source.h"))

    # Check the build folder
    assert os.path.exists(os.path.join(build_folder, "build.lib"))

    # Check the conaninfo
    assert os.path.exists(os.path.join(pf, "conaninfo.txt"))

    # Search the package in the cache
    client.run("search lib/1.0@")
    assert "Package_ID: 58083437fe22ef1faaa0ab4bb21d0a95bf28ae3d" in client.out

    # Install the package and check the build info
    client.run("install lib/1.0@ -g txt")
    binfopath = os.path.join(client.current_folder, "conanbuildinfo.txt")
    content = load(binfopath).replace("\r\n", "\n")
    assert "[includedirs]\n{}".format(os.path.join(pf, "include")
                                      .replace("\\", "/")) in content
    assert "[libdirs]\n{}".format(os.path.join(pf, "lib")
                                  .replace("\\", "/")) in content


def test_same_conanfile_local(conanfile):
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . base/1.0@")

    client.save({"conanfile.py": conanfile})

    source_folder = os.path.join(client.current_folder, "my_sources")
    build_folder = os.path.join(client.current_folder, "my_build")

    client.run("install . lib/1.0@ -if=install")
    client.run("source .  -if=install")
    assert "Source folder: {}".format(source_folder) in client.out
    assert os.path.exists(os.path.join(source_folder, "source.h"))

    client.run("build .  -if=install")
    assert "Build folder: {}".format(build_folder) in client.out
    assert os.path.exists(os.path.join(build_folder, "build.lib"))

    client.run("package .  -if=install")
    # By default, the "package" folder is still used (not breaking)
    pf = os.path.join(client.current_folder, "package")
    assert "Package folder: {}".format(pf) in client.out
    assert os.path.exists(os.path.join(pf, "LICENSE"))
