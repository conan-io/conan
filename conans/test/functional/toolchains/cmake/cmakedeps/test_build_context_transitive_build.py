import os
import textwrap

import pytest

from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient

"""
If we have a BR with transitive requires we won't generate 'xxx-config.cmake' files for them
but neither will be included as find_dependencies()
"""


@pytest.fixture
def client():
    c = TestClient()
    zlib_conanfile = textwrap.dedent('''
    from conans import ConanFile

    class Zlib(ConanFile):
        name = "zlib"
        version = "1.2.11"

        def package_info(self):
            self.cpp_info.includedirs = []
            self.cpp_info.cxxflags = ["foo"]
    ''')
    c.save({"conanfile.py": zlib_conanfile})
    c.run("create . ")

    doxygen_conanfile = textwrap.dedent('''
    from conans import ConanFile
    from conans.tools import save, chdir
    import os

    class Doxygen(ConanFile):
        settings = "build_type", "os", "arch", "compiler"
        requires = "zlib/1.2.11"

        def package(self):
            with chdir(self.package_folder):
                save("include/doxygen.h", "int foo=1;")
    ''')
    c.save({"conanfile.py": doxygen_conanfile})
    c.run("create . doxygen/1.0@")
    return c


def test_zlib_not_included(client):

    main = gen_function_cpp(name="main", include="doxygen.h")
    cmake = gen_cmakelists(find_package=["doxygen"], appsources=["main.cpp"], appname="main")

    conanfile_consumer = textwrap.dedent('''
        from conans import ConanFile
        from conan.tools.cmake import CMakeDeps

        class Consumer(ConanFile):
            settings = "build_type", "os", "arch", "compiler"
            build_requires = ["doxygen/1.0"]
            generators = "CMakeToolchain"

            def generate(self):
                d = CMakeDeps(self)
                d.build_context_activated = ["doxygen"]
                d.generate()
        ''')

    client.save({"main.cpp": main, "CMakeLists.txt": cmake, "conanfile.py": conanfile_consumer},
                clean_first=True)
    client.run("install . -pr:h=default -pr:b=default")
    # The compilation works, so it finds the doxygen without transitive failures
    client.run_command("cmake . -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake -DCMAKE_BUILD_TYPE=Release")

    # Assert there is no zlib target
    assert "Target declared 'zlib::zlib'" not in client.out

    # Of course we find the doxygen-config.cmake
    assert os.path.exists(os.path.join(client.current_folder, "doxygen-config.cmake"))

    # The -config files for zlib are not there
    assert not os.path.exists(os.path.join(client.current_folder, "zlib-config.cmake"))
