import os
import re
import textwrap

import pytest

from conans import load
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


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
        # The layout describes where the sources are, not force them to be there
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

    client.run("package .  -if=install", assert_error=True)
    assert "The usage of the 'conan package' local method is disabled when using " \
           "layout()" in client.out


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


def test_cpp_package():
    client = TestClient()

    conan_hello = textwrap.dedent("""
        import os
        from conans import ConanFile
        from conan.tools.files import save
        class Pkg(ConanFile):
            def package(self):
                save(self, os.path.join(self.package_folder, "foo/include/foo.h"), "")
                save(self, os.path.join(self.package_folder,"foo/libs/foo.lib"), "")

            def layout(self):
                self.cpp.package.includedirs = ["foo/include"]
                self.cpp.package.libdirs = ["foo/libs"]
                self.cpp.package.libs = ["foo"]
             """)

    client.save({"conanfile.py": conan_hello})
    client.run("create . hello/1.0@")
    ref = ConanFileReference.loads("hello/1.0")
    pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID)
    package_folder = client.cache.package_layout(pref.ref).package(pref).replace("\\", "/") + "/"

    conan_consumer = textwrap.dedent("""
        from conans import ConanFile
        class HelloTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            requires = "hello/1.0"
            generators = "CMakeDeps"
            def generate(self):
                info = self.dependencies["hello"].cpp_info
                self.output.warn("**includedirs:{}**".format(info.includedirs))
                self.output.warn("**libdirs:{}**".format(info.libdirs))
                self.output.warn("**libs:{}**".format(info.libs))
        """)

    client.save({"conanfile.py": conan_consumer})
    client.run("install .")
    out = str(client.out).replace(r"\\", "/").replace(package_folder, "")
    assert "**includedirs:['foo/include']**" in out
    assert "**libdirs:['foo/libs']**" in out
    assert "**libs:['foo']**" in out
    arch = client.get_default_host_profile().settings['arch']
    cmake = client.load(f"hello-release-{arch}-data.cmake")

    assert 'set(hello_INCLUDE_DIRS_RELEASE "${hello_PACKAGE_FOLDER_RELEASE}/foo/include")' in cmake
    assert 'set(hello_LIB_DIRS_RELEASE "${hello_PACKAGE_FOLDER_RELEASE}/foo/libs")' in cmake
    assert 'set(hello_LIBS_RELEASE foo)' in cmake


def test_git_clone_with_source_layout():
    client = TestClient()
    repo = temp_folder()
    conanfile = textwrap.dedent("""
           import os
           from conans import ConanFile
           class Pkg(ConanFile):
               exports_sources = "*.txt"

               def layout(self):
                   self.folders.source = "src"

               def source(self):
                   self.run('git clone "{}" .')
       """).format(repo.replace("\\", "/"))

    client.save({"conanfile.py": conanfile,
                 "myfile.txt": "My file is copied"})
    with client.chdir(repo):
        client.save({"cloned.txt": "foo"}, repo)
        client.init_git_repo()

    client.run("create . hello/1.0@")
    sf = client.cache.package_layout(ConanFileReference.loads("hello/1.0@")).source()
    assert os.path.exists(os.path.join(sf, "myfile.txt"))
    # The conanfile is cleared from the root before cloning
    assert not os.path.exists(os.path.join(sf, "conanfile.py"))
    assert not os.path.exists(os.path.join(sf, "cloned.txt"))

    assert os.path.exists(os.path.join(sf, "src", "cloned.txt"))
    assert not os.path.exists(os.path.join(sf, "src", "myfile.txt"))
