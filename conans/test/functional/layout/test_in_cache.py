import os
import re
import textwrap

import pytest

from conans import load
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.fixture
def conanfile():
    conan_file = str(GenConanfile().with_import("from conans import tools").with_import("import os").
                     with_require("base/1.0"))

    conan_file += """
    no_copy_sources = True

    def layout(self):
        self.folders.source = "my_sources"
        self.folders.build = "my_build"

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
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.libdirs = ["lib"]
    """
    return conan_file


def test_create_test_package_no_layout(conanfile):
    """The test package using the new generators work (having the generated files in the build
    folder)"""
    client = TestClient()
    conanfile_test = textwrap.dedent("""
        import os

        from conans import ConanFile, tools

        class HelloTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps", "CMakeToolchain"
            def build(self):
                assert os.path.exists("conan_toolchain.cmake")
                self.output.warn("hey! building")
                self.output.warn(os.getcwd())

            def test(self):
                self.output.warn("hey! testing")
    """)
    client.save({"conanfile.py": GenConanfile(), "test_package/conanfile.py": conanfile_test})
    client.run("create . lib/1.0@")
    assert "hey! building" in client.out
    assert "hey! testing" in client.out


def test_create_test_package_with_layout(conanfile):
    """The test package using the new generators work (having the generated files in the build
    folder)"""
    client = TestClient()
    conanfile_test = textwrap.dedent("""
        import os

        from conans import ConanFile, tools
        from conan.tools.cmake import CMakeToolchain, CMake, CMakeDeps

        class HelloTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"

            def generate(self):
                deps = CMakeDeps(self)
                deps.generate()
                tc = CMakeToolchain(self)
                tc.generate()

            def layout(self):
                self.folders.generators = "my_generators"

            def build(self):
                assert os.path.exists("my_generators/conan_toolchain.cmake")
                self.output.warn("hey! building")
                self.output.warn(os.getcwd())

            def test(self):
                self.output.warn("hey! testing")
    """)
    client.save({"conanfile.py": GenConanfile(), "test_package/conanfile.py": conanfile_test})
    client.run("create . lib/1.0@")
    assert "hey! building" in client.out
    assert "hey! testing" in client.out


@pytest.mark.xfail(reason="This test will not pass because during build we use a temporal folder"
                          "with the new Cache2.0. TODO: cache2.0 must adapt")
def test_cache_in_layout(conanfile):
    """The layout in the cache is used too, always relative to the "base" folders that the cache
    requires. But by the default, the "package" is not followed
    """
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . base/1.0@")

    client.save({"conanfile.py": conanfile})
    client.run("create . lib/1.0@")
    package_id = re.search(r"lib/1.0:(\S+)", str(client.out)).group(1)
    ref = ConanFileReference.loads("lib/1.0@")
    pref = PackageReference(ref, package_id)
    sf = client.cache.package_layout(ref).source()
    bf = client.cache.package_layout(ref).build(pref)
    pf = client.cache.package_layout(ref).package(pref)

    source_folder = os.path.join(sf, "my_sources")
    build_folder = os.path.join(bf, "my_build")

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
    assert "Package_ID: {}".format(package_id) in client.out


def test_same_conanfile_local(conanfile):
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . base/1.0@")

    client.save({"conanfile.py": conanfile})

    source_folder = os.path.join(client.current_folder, "my_sources")
    build_folder = os.path.join(client.current_folder, "my_build")

    client.run("install . lib/1.0@ -if=install")
    client.run("source .")
    assert "Source folder: {}".format(source_folder) in client.out
    assert os.path.exists(os.path.join(source_folder, "source.h"))

    client.run("build .  -if=install")
    assert "Build folder: {}".format(build_folder) in client.out
    assert os.path.exists(os.path.join(build_folder, "build.lib"))


def test_imports():
    """The 'conan imports' follows the layout"""
    client = TestClient()
    # Hello to be reused
    conan_file = str(GenConanfile().with_import("from conans import tools"))
    conan_file += """
    no_copy_source = True

    def build(self):
        tools.save("library.dll", "bar")
        tools.save("generated.h", "bar")

    def package(self):
        self.copy("*.h")
        self.copy("*.dll")
    """
    client.save({"conanfile.py": conan_file})
    client.run("create . hello/1.0@")

    # Consumer of the hello importing the shared
    conan_file = str(GenConanfile().with_import("from conans import tools").with_import("import os"))
    conan_file += """
    no_copy_source = True
    requires = "hello/1.0"
    settings = "build_type"

    def layout(self):
        self.folders.build = "cmake-build-{}".format(str(self.settings.build_type).lower())
        self.folders.imports = os.path.join(self.folders.build, "my_imports")

    def imports(self):
        self.output.warn("Imports folder: {}".format(self.imports_folder))
        self.copy("*.dll")

    def build(self):
        assert self.build_folder != self.imports_folder
        assert "cmake-build-release" in self.build_folder
        assert os.path.exists(os.path.join(self.imports_folder, "library.dll"))
        assert os.path.exists(os.path.join(self.build_folder, "my_imports", "library.dll"))
        self.output.warn("Built and imported!")
    """

    client.save({"conanfile.py": conan_file})
    client.run("create . consumer/1.0@ ")
    assert "Built and imported!" in client.out
