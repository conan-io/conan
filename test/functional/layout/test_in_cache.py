import os
import textwrap

import pytest

from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


@pytest.fixture
def conanfile():
    conan_file = str(GenConanfile()
                     .with_import("import os")
                     .with_import("from conan.tools.files import copy, save").
                     with_require("base/1.0"))

    conan_file += """
    no_copy_sources = True

    def layout(self):
        self.folders.source = "my_sources"
        self.folders.build = "my_build"

    def source(self):
        self.output.warning("Source folder: {}".format(self.source_folder))
        # The layout describes where the sources are, not force them to be there
        save(self, "source.h", "foo")

    def build(self):
        self.output.warning("Build folder: {}".format(self.build_folder))
        save(self, "build.lib", "bar")

    def package(self):
        self.output.warning("Package folder: {}".format(self.package_folder))
        save(self, os.path.join(self.package_folder, "LICENSE"), "bar")
        copy(self, "*.h", self.source_folder, os.path.join(self.package_folder, "include"))
        copy(self, "*.lib", self.build_folder, os.path.join(self.package_folder, "lib"))

    def package_info(self):
        # This will be easier when the layout declares also the includedirs etc
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.libdirs = ["lib"]
    """
    return conan_file


def test_create_test_package_no_layout():
    """The test package using the new generators work (having the generated files in the build
    folder)"""
    client = TestClient()
    conanfile_test = textwrap.dedent("""
        import os

        from conan import ConanFile, tools

        class HelloTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps", "CMakeToolchain"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def build(self):
                assert os.path.exists("conan_toolchain.cmake")
                self.output.warning("hey! building")
                self.output.warning(os.getcwd())

            def test(self):
                self.output.warning("hey! testing")
    """)
    client.save({"conanfile.py": GenConanfile(), "test_package/conanfile.py": conanfile_test})
    client.run("create . --name=lib --version=1.0")
    assert "hey! building" in client.out
    assert "hey! testing" in client.out


def test_create_test_package_with_layout():
    """The test package using the new generators work (having the generated files in the build
    folder)"""
    client = TestClient()
    conanfile_test = textwrap.dedent("""
        import os

        from conan import ConanFile, tools
        from conan.tools.cmake import CMakeToolchain, CMake, CMakeDeps

        class HelloTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def generate(self):
                deps = CMakeDeps(self)
                deps.generate()
                tc = CMakeToolchain(self)
                tc.generate()

            def layout(self):
                self.folders.generators = "my_generators"

            def build(self):
                assert os.path.exists("my_generators/conan_toolchain.cmake")
                self.output.warning("hey! building")
                self.output.warning(os.getcwd())

            def test(self):
                self.output.warning("hey! testing")
    """)
    client.save({"conanfile.py": GenConanfile(), "test_package/conanfile.py": conanfile_test})
    client.run("create . --name=lib --version=1.0")
    assert "hey! building" in client.out
    assert "hey! testing" in client.out


def test_cache_in_layout(conanfile):
    """The layout in the cache is used too, always relative to the "base" folders that the cache
    requires. But by the default, the "package" is not followed
    """
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=base --version=1.0")

    client.save({"conanfile.py": conanfile})
    client.run("create . --name=lib --version=1.0")
    pkg_layout = client.created_layout()
    sf = client.exported_layout().source()
    bf = pkg_layout.build()
    pf = pkg_layout.package()

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


def test_same_conanfile_local(conanfile):
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=base --version=1.0")

    client.save({"conanfile.py": conanfile})

    source_folder = os.path.join(client.current_folder, "my_sources")
    build_folder = os.path.join(client.current_folder, "install", "my_build")

    client.run("install . --name=lib --version=1.0 -of=install")
    client.run("source .")
    assert "Source folder: {}".format(source_folder) in client.out
    assert os.path.exists(os.path.join(source_folder, "source.h"))

    client.run("build .  -of=install")
    assert "Build folder: {}".format(build_folder) in client.out
    assert os.path.exists(os.path.join(build_folder, "build.lib"))


def test_cpp_package():
    client = TestClient()

    conan_hello = textwrap.dedent("""
        import os
        from conan import ConanFile
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
    client.run("create . --name=hello --version=1.0")
    rrev = client.exported_recipe_revision()
    ref = RecipeReference.loads("hello/1.0")
    ref.revision = rrev
    pref = PkgReference(ref, NO_SETTINGS_PACKAGE_ID)
    package_folder = client.get_latest_pkg_layout(pref).package().replace("\\", "/") + "/"

    conan_consumer = textwrap.dedent("""
        from conan import ConanFile
        class HelloTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            requires = "hello/1.0"
            generators = "CMakeDeps"
            def generate(self):
                info = self.dependencies["hello"].cpp_info
                self.output.warning("**includedirs:{}**".format(info.includedirs))
                self.output.warning("**libdirs:{}**".format(info.libdirs))
                self.output.warning("**libs:{}**".format(info.libs))
        """)

    client.save({"conanfile.py": conan_consumer})
    client.run("install .")
    out = str(client.out).replace(r"\\", "/").replace(package_folder, "")
    assert "**includedirs:['foo/include']**" in out
    assert "**libdirs:['foo/libs']**" in out
    assert "**libs:['foo']**" in out
    host_arch = client.get_default_host_profile().settings['arch']
    cmake = client.load(f"hello-release-{host_arch}-data.cmake")

    assert 'set(hello_INCLUDE_DIRS_RELEASE "${hello_PACKAGE_FOLDER_RELEASE}/foo/include")' in cmake
    assert 'set(hello_LIB_DIRS_RELEASE "${hello_PACKAGE_FOLDER_RELEASE}/foo/libs")' in cmake
    assert 'set(hello_LIBS_RELEASE foo)' in cmake


def test_git_clone_with_source_layout():
    client = TestClient()
    repo = temp_folder()
    conanfile = textwrap.dedent("""
           import os
           from conan import ConanFile
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

    client.run("create . --name=hello --version=1.0")
    sf = client.exported_layout().source()
    assert os.path.exists(os.path.join(sf, "myfile.txt"))
    # The conanfile is cleared from the root before cloning
    assert not os.path.exists(os.path.join(sf, "conanfile.py"))
    assert not os.path.exists(os.path.join(sf, "cloned.txt"))

    assert os.path.exists(os.path.join(sf, "src", "cloned.txt"))
    assert not os.path.exists(os.path.join(sf, "src", "myfile.txt"))
