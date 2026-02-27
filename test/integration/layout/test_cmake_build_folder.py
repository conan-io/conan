import os
import re
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("cmd", ["install", "build"])
def test_cmake_layout_build_folder(cmd):
    """ testing the tools.cmake.cmake_layout:build_folder config for
    both build and install commands
    """
    c = TestClient()
    abs_build = temp_folder()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class HelloTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"
            def layout(self):
                cmake_layout(self, generator="Ninja")  # Ninja so same in all OSs, single-config
        """)

    c.save({"conanfile.py": conanfile})
    c.run(f'{cmd} . -c tools.cmake.cmake_layout:build_folder="{abs_build}"')
    assert os.path.exists(os.path.join(abs_build, "Release", "generators", "conan_toolchain.cmake"))
    assert not os.path.exists(os.path.join(c.current_folder, "build"))

    # Make sure that a non-existing folder will not fail and will be created
    new_folder = os.path.join(temp_folder(), "my build")
    c.run(f'{cmd} . -c tools.cmake.cmake_layout:build_folder="{new_folder}"')
    assert os.path.exists(os.path.join(new_folder, "Release", "generators", "conan_toolchain.cmake"))
    assert not os.path.exists(os.path.join(c.current_folder, "build"))

    # Just in case we check that local build folder would be created if no arg is provided
    c.run('build . ')
    assert os.path.exists(os.path.join(c.current_folder, "build"))


@pytest.mark.parametrize("cmd", ["install", "build"])
def test_cmake_layout_build_folder_relative(cmd):
    """ Same as above, but with a relative folder, which is relative to the conanfile
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class HelloTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"
            def layout(self):
                cmake_layout(self, generator="Ninja")  # Ninja so same in all OSs, single-config
        """)

    c.save({"pkg/conanfile.py": conanfile})
    c.run(f'{cmd} pkg -c tools.cmake.cmake_layout:build_folder=mybuild')
    abs_build = os.path.join(c.current_folder, "pkg", "mybuild")
    assert os.path.exists(os.path.join(abs_build, "Release", "generators", "conan_toolchain.cmake"))
    assert not os.path.exists(os.path.join(c.current_folder, "pkg", "build"))

    # relative path, pointing to a sibling folder
    c.run(f'{cmd} pkg -c tools.cmake.cmake_layout:build_folder=../mybuild')
    abs_build = os.path.join(c.current_folder, "mybuild")
    assert os.path.exists(os.path.join(abs_build, "Release", "generators", "conan_toolchain.cmake"))
    assert not os.path.exists(os.path.join(c.current_folder, "build"))

    # Just in case we check that local build folder would be created if no arg is provided
    c.run('build pkg ')
    assert os.path.exists(os.path.join(c.current_folder, "pkg", "build"))


def test_test_cmake_layout_build_folder_test_package():
    """ relocate the test_package temporary build folders to elsewhere
    """
    c = TestClient()
    abs_build = temp_folder()
    test_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class HelloTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def layout(self):
                cmake_layout(self, generator="Ninja")

            def test(self):
                pass
        """)

    c.save({"conanfile.py": GenConanfile("pkg", "0.1"),
            "test_package/conanfile.py": test_conanfile})
    c.run(f'create . -c tools.cmake.cmake_layout:test_folder="{abs_build}" '
          '-c tools.cmake.cmake_layout:build_folder_vars=[]')
    # Even if build_folder_vars=[] the "Release" folder is added always
    assert os.path.exists(os.path.join(abs_build, "Release", "generators", "conan_toolchain.cmake"))
    assert not os.path.exists(os.path.join(c.current_folder, "test_package", "build"))

    c.run(f'create . -c tools.cmake.cmake_layout:build_folder_vars=[]')
    assert os.path.exists(os.path.join(c.current_folder, "test_package", "build"))


def test_test_cmake_layout_build_folder_test_package_temp():
    """ using always the same test_package build_folder will cause collisions.
    We need a mechanism to relocate, still provide unique folders for each build
    """
    c = TestClient()
    test_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class HelloTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def layout(self):
                cmake_layout(self)

            def test(self):
                pass
        """)

    profile = textwrap.dedent("""
        include(default)
        [conf]
        tools.cmake.cmake_layout:test_folder=$TMP
        tools.cmake.cmake_layout:build_folder_vars=[]
        """)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1"),
            "test_package/conanfile.py": test_conanfile,
            "profile": profile})
    c.run(f'create . -pr=profile')
    build_folder = re.search(r"Test package build folder: (\S+)", str(c.out)).group(1)
    assert os.path.exists(os.path.join(build_folder, "generators", "conan_toolchain.cmake"))
    assert not os.path.exists(os.path.join(c.current_folder, "test_package", "build"))

    c.run(f'test test_package pkg/0.1 -pr=profile')
    build_folder = re.search(r"Test package build folder: (\S+)", str(c.out)).group(1)
    assert os.path.exists(os.path.join(build_folder, "generators", "conan_toolchain.cmake"))
    assert not os.path.exists(os.path.join(c.current_folder, "test_package", "build"))

    c.run(f'create . -c tools.cmake.cmake_layout:build_folder_vars=[]')
    assert os.path.exists(os.path.join(c.current_folder, "test_package", "build"))


def test_cmake_layout_build_folder_editable():
    """ testing how it works with editables. Layout
    code
      pkga  # editable add .
      pkgb  # editable add .
      app   # install -c build_folder="../../mybuild -c build_folder_vars="['self.name']"
        pkga-release-data.cmake
           pkga_PACKAGE_FOLDER_RELEASE = /abs/path/to/code/pkga
           pkga_INCLUDE_DIRS_RELEASE   = ${pkga_PACKAGE_FOLDER_RELEASE}/include
           pkga_LIB_DIRS_RELEASE =       /abs/path/to/mybuild/pkga/Release
    mybuild
      pkga/Release/
      pkgb/Release/
    """
    c = TestClient()
    base_folder = temp_folder()
    c.current_folder = os.path.join(base_folder, "code").replace("\\", "/")
    project_build_folder = os.path.join(base_folder, "mybuild").replace("\\", "/")
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class Pkg(ConanFile):
            name = "{name}"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"
            def layout(self):
                cmake_layout(self, generator="Ninja")  # Ninja so same in all OSs, single-config
        """)

    c.save({"pkga/conanfile.py": conanfile.format(name="pkga"),
            "pkgb/conanfile.py": conanfile.format(name="pkgb"),
            "app/conanfile.py": GenConanfile().with_requires("pkga/0.1", "pkgb/0.1")
                                              .with_settings("build_type")
                                              .with_generator("CMakeDeps")})

    c.run("editable add pkga")
    c.run("editable add pkgb")
    conf = f'-c tools.cmake.cmake_layout:build_folder="../../mybuild" ' \
           '-c tools.cmake.cmake_layout:build_folder_vars="[\'self.name\']"'
    c.run(f'install app {conf} --build=editable')

    data = c.load("app/pkga-release-data.cmake")

    # The package is the ``code/pkga`` folder
    assert f'pkga_PACKAGE_FOLDER_RELEASE "{c.current_folder}/pkga"' in data
    # This is an absolute path, not relative, as it is not inside the package
    assert f'set(pkga_LIB_DIRS_RELEASE "{project_build_folder}/pkga/Release' in data
    data = c.load("app/pkgb-release-data.cmake")
    assert f'set(pkgb_LIB_DIRS_RELEASE "{project_build_folder}/pkgb/Release' in data

    assert os.path.exists(os.path.join(project_build_folder, "pkga", "Release", "generators",
                                       "conan_toolchain.cmake"))
    assert os.path.exists(os.path.join(project_build_folder, "pkgb", "Release", "generators",
                                       "conan_toolchain.cmake"))


def test_cmake_layout_editable_output_folder():
    """ testing how it works with editables, but --output-folder
    code
      pkga  # editable add . --output-folder = ../mybuild
      pkgb  # editable add . --output-folder = ../mybuild
      app   # install  -c build_folder_vars="['self.name']"
        pkga-release-data.cmake
           pkga_PACKAGE_FOLDER_RELEASE = /abs/path/to/mybuild
           pkga_INCLUDE_DIRS_RELEASE   = /abs/path/to/code/pkga/include
           pkga_LIB_DIRS_RELEASE =       pkga_PACKAGE_FOLDER_RELEASE/build/pkga/Release
    mybuild
      build
        pkga/Release/
        pkgb/Release/
    """
    c = TestClient()
    base_folder = temp_folder()
    c.current_folder = os.path.join(base_folder, "code")
    project_build_folder = os.path.join(base_folder, "mybuild").replace("\\", "/")
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class Pkg(ConanFile):
            name = "{name}"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"
            def layout(self):
                cmake_layout(self, generator="Ninja")  # Ninja so same in all OSs, single-config
        """)

    c.save({"pkga/conanfile.py": conanfile.format(name="pkga"),
            "pkgb/conanfile.py": conanfile.format(name="pkgb"),
            "app/conanfile.py": GenConanfile().with_requires("pkga/0.1", "pkgb/0.1")
           .with_settings("build_type")
           .with_generator("CMakeDeps")})

    c.run(f'editable add pkga --output-folder="../mybuild"')
    c.run(f'editable add pkgb --output-folder="../mybuild"')
    conf = f'-c tools.cmake.cmake_layout:build_folder_vars="[\'self.name\']"'
    c.run(f'install app {conf} --build=editable')

    data = c.load("app/pkga-release-data.cmake")
    assert f'set(pkga_PACKAGE_FOLDER_RELEASE "{project_build_folder}")' in data
    # Thse folders are relative to the package
    assert 'pkga_LIB_DIRS_RELEASE "${pkga_PACKAGE_FOLDER_RELEASE}/build/pkga/Release' in data
    data = c.load("app/pkgb-release-data.cmake")
    assert 'pkgb_LIB_DIRS_RELEASE "${pkgb_PACKAGE_FOLDER_RELEASE}/build/pkgb/Release' in data

    assert os.path.exists(os.path.join(project_build_folder, "build", "pkga", "Release",
                                       "generators", "conan_toolchain.cmake"))
    assert os.path.exists(os.path.join(project_build_folder, "build", "pkgb", "Release",
                                       "generators", "conan_toolchain.cmake"))
