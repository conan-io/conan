import os
import re
import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


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
    assert os.path.exists(os.path.join(abs_build, "release", "generators", "conan_toolchain.cmake"))
    assert not os.path.exists(os.path.join(c.current_folder, "build"))

    # Make sure that a non-existing folder will not fail and will be created
    new_folder = os.path.join(temp_folder(), "my build")
    c.run(f'{cmd} . -c tools.cmake.cmake_layout:build_folder="{new_folder}"')
    assert os.path.exists(os.path.join(new_folder, "release", "generators", "conan_toolchain.cmake"))
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
    assert os.path.exists(os.path.join(abs_build, "release", "generators", "conan_toolchain.cmake"))
    assert not os.path.exists(os.path.join(c.current_folder, "pkg", "build"))

    # relative path, pointing to a sibling folder
    c.run(f'{cmd} pkg -c tools.cmake.cmake_layout:build_folder=../mybuild')
    abs_build = os.path.join(c.current_folder, "mybuild")
    assert os.path.exists(os.path.join(abs_build, "release", "generators", "conan_toolchain.cmake"))
    assert not os.path.exists(os.path.join(c.current_folder, "build"))

    # Just in case we check that local build folder would be created if no arg is provided
    c.run('build pkg ')
    assert os.path.exists(os.path.join(c.current_folder, "pkg", "build"))


def test_test_cmake_layout_build_folder_test_package():
    """ it also works to relocate the test_package temporary build folders to elsewhere
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
                cmake_layout(self)

            def test(self):
                pass
        """)

    c.save({"conanfile.py": GenConanfile("pkg", "0.1"),
            "test_package/conanfile.py": test_conanfile})
    c.run(f'create . -c tools.cmake.cmake_layout:build_folder="{abs_build}" '
          '-c tools.cmake.cmake_layout:build_folder_vars=[]')
    assert os.path.exists(os.path.join(abs_build, "generators", "conan_toolchain.cmake"))
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
        tools.cmake.cmake_layout:build_folder={{tempfile.mkdtemp()}}
        tools.cmake.cmake_layout:build_folder_vars=[]
        """)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1"),
            "test_package/conanfile.py": test_conanfile,
            "profile": profile})
    c.run(f'create . -pr=profile')
    build_folder = re.search(r"Test package build folder: (\S+)", str(c.out)).group(1)
    assert os.path.exists(os.path.join(build_folder, "generators", "conan_toolchain.cmake"))
    assert not os.path.exists(os.path.join(c.current_folder, "test_package", "build"))

    c.run(f'create . -c tools.cmake.cmake_layout:build_folder_vars=[]')
    assert os.path.exists(os.path.join(c.current_folder, "test_package", "build"))
