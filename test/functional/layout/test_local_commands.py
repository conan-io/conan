import os
import platform
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.assets.pkg_cmake import pkg_cmake
from conan.test.utils.tools import TestClient


def test_local_static_generators_folder():
    """If we configure a generators folder in the layout, the generator files:
      - If belong to new generators: go to the specified folder: "my_generators"
      - If belong to old generators or txt: remains in the install folder
    """
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type"))
    conan_file += """
    generators = "CMakeToolchain"
    def layout(self):
        self.folders.build = "build-{}".format(self.settings.build_type)
        self.folders.generators = "{}/generators".format(self.folders.build)
    """
    client.save({"conanfile.py": conan_file})
    client.run("install . -of=my_install")

    old_install_folder = os.path.join(client.current_folder, "my_install")
    cmake_toolchain_generator_path = os.path.join(old_install_folder, "conan_toolchain.cmake")
    assert not os.path.exists(cmake_toolchain_generator_path)

    build_folder = os.path.join(client.current_folder, "my_install", "build-Release")
    generators_folder = os.path.join(build_folder, "generators")
    cmake_toolchain_generator_path = os.path.join(generators_folder, "conan_toolchain.cmake")
    assert os.path.exists(cmake_toolchain_generator_path)


def test_local_dynamic_generators_folder():
    """If we configure a generators folder in the layout, the generator files:
      - If belong to new generators: go to the specified folder: "my_generators"
      - "txt" and old ones always to the install folder
    """
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type").
                     with_import("from conan.tools.cmake import CMakeToolchain, CMake"))
    conan_file += """
    def generate(self):
        tc = CMakeToolchain(self)
        tc.generate()
    def layout(self):
        self.folders.build = "build-{}".format(self.settings.build_type)
        self.folders.generators = "{}/generators".format(self.folders.build)
    """
    client.save({"conanfile.py": conan_file})
    client.run("install . -of=my_install")

    old_install_folder = os.path.join(client.current_folder, "my_install")
    cmake_toolchain_generator_path = os.path.join(old_install_folder, "conan_toolchain.cmake")
    assert not os.path.exists(cmake_toolchain_generator_path)

    build_folder = os.path.join(client.current_folder, "my_install", "build-Release")
    generators_folder = os.path.join(build_folder, "generators")
    cmake_toolchain_generator_path = os.path.join(generators_folder, "conan_toolchain.cmake")
    assert os.path.exists(cmake_toolchain_generator_path)


def test_no_layout_generators_folder():
    """If we don't configure a generators folder in the layout, the generator files:
      - all go to the install_folder
    """
    client = TestClient()
    conan_file = str(GenConanfile().with_settings("build_type").
                     with_import("from conan.tools.cmake import CMakeToolchain, CMake"))
    conan_file += """
    def generate(self):
        tc = CMakeToolchain(self)
        tc.generate()
    """
    client.save({"conanfile.py": conan_file})
    client.run("install . -of=my_install")

    old_install_folder = os.path.join(client.current_folder, "my_install")
    cmake_toolchain_generator_path = os.path.join(old_install_folder, "conan_toolchain.cmake")

    # In the install_folder
    assert os.path.exists(cmake_toolchain_generator_path)

    # But not in the base folder
    assert not os.path.exists(os.path.join(client.current_folder, "conan_toolchain.cmake"))


def test_local_build():
    """If we configure a build folder in the layout, the installed files in a "conan build ."
    go to the specified folder: "my_build"
    """
    client = TestClient()
    conan_file = str(GenConanfile().with_import("from conan.tools.files import save"))
    conan_file += """
    def layout(self):
        self.folders.generators = "my_generators"
        self.folders.build = "my_build"
    def build(self):
        self.output.warning("Generators folder: {}".format(self.folders.generators_folder))
        save(self, "build_file.dll", "bar")
"""
    client.save({"conanfile.py": conan_file})
    client.run("build . --output-folder=my_install")
    dll = os.path.join(client.current_folder, "my_install", "my_build", "build_file.dll")
    assert os.path.exists(dll)


def test_local_build_change_base():
    """If we configure a build folder in the layout, the build files in a "conan build ."
    go to the specified folder: "my_build under the modified base one "common"
    """
    client = TestClient()
    conan_file = str(GenConanfile().with_import("from conan.tools.files import save"))
    conan_file += """
    def layout(self):
        self.folders.build = "my_build"
    def build(self):
        save(self, "build_file.dll", "bar")
    """
    client.save({"conanfile.py": conan_file})
    client.run("install . --output-folder=common")
    client.run("build . --output-folder=common")
    dll = os.path.join(client.current_folder, "common", "my_build", "build_file.dll")
    assert os.path.exists(dll)


def test_local_source():
    """The "conan source" is NOT affected by the --output-folder
    """
    client = TestClient()
    conan_file = str(GenConanfile().with_import("from conan.tools.files import save"))
    conan_file += """
    def layout(self):
        self.folders.source = "my_source"
    def source(self):
        save(self, "downloaded.h", "bar")
    """
    client.save({"conanfile.py": conan_file})
    client.run("install . -of=my_install")
    client.run("source .")
    header = os.path.join(client.current_folder, "my_source", "downloaded.h")
    assert os.path.exists(header)


def test_export_pkg():
    """The export-pkg, calling the "package" method, follows the layout if `cache_package_layout` """
    client = TestClient()
    conan_file = str(GenConanfile("lib", "1.0")
                     .with_import("from conan.tools.files import copy, save"))
    conan_file += """
    no_copy_source = True
    def layout(self):
        self.folders.source = "my_source"
        self.folders.build = "my_build"
    def source(self):
        save(self, "downloaded.h", "bar")
    def build(self):
        save(self, "library.lib", "bar")
        save(self, "generated.h", "bar")
    def package(self):
        copy(self, "*.h", self.source_folder, self.package_folder)
        copy(self, "*.h", self.build_folder, self.package_folder)
        copy(self, "*.lib", self.build_folder, self.package_folder)
    """

    client.save({"conanfile.py": conan_file})
    client.run("source .")
    client.run("build .")
    client.run("export-pkg .")

    pf = client.created_layout().package()

    # Check the artifacts packaged
    assert os.path.exists(os.path.join(pf, "downloaded.h"))
    assert os.path.exists(os.path.join(pf, "generated.h"))
    assert os.path.exists(os.path.join(pf, "library.lib"))


def test_export_pkg_local():
    """The export-pkg, without calling "package" method, with local package, follows the layout"""
    client = TestClient()
    conan_file = str(GenConanfile("lib", "1.0")
                     .with_import("from conan.tools.files import copy, save"))
    conan_file += """
    no_copy_source = True
    def layout(self):
        self.folders.source = "my_source"
        self.folders.build = "my_build"
        self.folders.package = "my_package"
    def source(self):
        save(self, "downloaded.h", "bar")
    def build(self):
        save(self, "library.lib", "bar")
        save(self, "generated.h", "bar")
    def package(self):
        copy(self, "*.h", self.source_folder, self.package_folder)
        copy(self, "*.h", self.build_folder, self.package_folder)
        copy(self, "*.lib", self.build_folder, self.package_folder)
    """

    client.save({"conanfile.py": conan_file})
    client.run("source .")
    client.run("build .")

    # assert "WARN: Package folder: {}".format(pf) in client.out

    client.run("export-pkg .")
    pf = client.created_layout().package()

    # Check the artifacts packaged, THERE IS NO "my_package" in the cache
    assert "my_package" not in pf
    assert os.path.exists(os.path.join(pf, "downloaded.h"))
    assert os.path.exists(os.path.join(pf, "generated.h"))
    assert os.path.exists(os.path.join(pf, "library.lib"))

    # Doing a conan create: Same as export-pkg, there is "my_package" in the cache
    client.run("create . ")
    pf = client.created_layout().package()
    assert "my_package" not in pf
    assert os.path.exists(os.path.join(pf, "downloaded.h"))
    assert os.path.exists(os.path.join(pf, "generated.h"))
    assert os.path.exists(os.path.join(pf, "library.lib"))


def test_start_dir_failure():
    c = TestClient()
    c.save(pkg_cmake("dep", "0.1"))
    c.run("install .")
    if platform.system() != "Windows":
        gen_folder = os.path.join(c.current_folder, "build", "Release", "generators")
    else:
        gen_folder = os.path.join(c.current_folder, "build", "generators")
    expected_path = os.path.join(gen_folder, "conan_toolchain.cmake")
    assert os.path.exists(expected_path)
    os.unlink(expected_path)
    with c.chdir("build"):
        c.run("install ..")
    assert os.path.exists(expected_path)


def test_local_folders_without_layout():
    """ Test that the "conan install" can report the local source and build folder
    """
    # https://github.com/conan-io/conan/issues/10566
    client = TestClient()
    conan_file = textwrap.dedent("""
        from conan import ConanFile
        class Test(ConanFile):
            version = "1.2.3"
            name = "test"

            def layout(self):
                self.folders.source = "."
                self.folders.build = "build"

            def generate(self):
                self.output.info("generate sf: {}".format(self.source_folder))
                self.output.info("generate bf: {}".format(self.build_folder))
        """)

    client.save({"conanfile.py": conan_file})
    client.run("install .")
    assert "conanfile.py (test/1.2.3): generate sf: {}".format(client.current_folder) in client.out
    assert "conanfile.py (test/1.2.3): generate bf: {}".format(client.current_folder) in client.out
