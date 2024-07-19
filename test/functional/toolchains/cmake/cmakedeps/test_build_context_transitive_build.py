import os
import textwrap

import pytest

from conan.test.assets.cmake import gen_cmakelists
from conan.test.assets.genconanfile import GenConanfile
from conan.test.assets.pkg_cmake import pkg_cmake, pkg_cmake_app
from conan.test.assets.sources import gen_function_cpp
from conan.test.utils.tools import TestClient

"""
If we have a BR with transitive requires we won't generate 'xxx-config.cmake' files for them
but neither will be included as find_dependencies()
"""


@pytest.fixture
def client():
    c = TestClient()
    zlib_conanfile = textwrap.dedent('''
    from conan import ConanFile

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
    from conan import ConanFile
    from conan.tools.files import save, chdir
    import os

    class Doxygen(ConanFile):
        settings = "build_type", "os", "arch", "compiler"
        requires = "zlib/1.2.11"

        def package(self):
            with chdir(self, self.package_folder):
                save(self, "include/doxygen.h", "int foo=1;")
    ''')
    c.save({"conanfile.py": doxygen_conanfile})
    c.run("create . --name=doxygen --version=1.0")
    return c


@pytest.mark.tool("cmake")
def test_zlib_not_included(client):

    main = gen_function_cpp(name="main", includes=["doxygen.h"])
    cmake = gen_cmakelists(find_package=["doxygen"], appsources=["main.cpp"], appname="main")

    conanfile_consumer = textwrap.dedent('''
        from conan import ConanFile
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


def test_error_cmakedeps_transitive_build_requires():
    """
    CMakeDeps when building an intermediate "tool_requires" that has a normal "requires"
    to other package, needs to use ``require.build`` trait instead of the more global
    "dep.is_build_context"
    We do build "protobuf" in the "build" context to make sure the whole CMakeDeps is
    working correctly
    """
    c = TestClient()
    c.save(pkg_cmake("zlib", "0.1"))
    c.run("create .")
    c.save(pkg_cmake("openssl", "0.1", requires=["zlib/0.1"]), clean_first=True)
    c.run("create .")
    # Protobuf binary is missing, to force a build below with ``--build=missing``
    c.save(pkg_cmake_app("protobuf", "0.1", requires=["openssl/0.1"]), clean_first=True)
    c.run("export .")

    # This conanfile used to fail, creating protobuf_mybuild*.cmake files even if for "tool" the
    # protobuf/0.1 is a regular "requires" and it is in its host context
    # TODO: This approach still not works in 1.X when using simultaneously the same require
    #  and tool_requires over a tool_requires that needs to be built from source
    tool = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMakeDeps

        class Tool(ConanFile):
            name = "tool"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"
            requires = "protobuf/0.1"

            def generate(self):
                deps = CMakeDeps(self)
                deps.build_context_activated = ["protobuf"]
                deps.build_context_suffix = {"protobuf": "_mybuild"}
                deps.generate()

            def build(self):
                assert os.path.exists("protobufTargets.cmake")
                assert os.path.exists("protobuf-Target-release.cmake")
        """)
    c.save({"tool/conanfile.py": tool,
            "consumer/conanfile.py": GenConanfile().with_build_requires("tool/0.1")},
           clean_first=True)
    c.run("export tool")
    c.run("install consumer --build=missing -s:b build_type=Release -s:h build_type=Debug")
    assert "tool/0.1: Created package" in c.out


def test_transitive_tool_requires_visible():
    # https://github.com/conan-io/conan/issues/16058
    # The "tool/0.1", even if visible doesn't generate any files in the "app" consumer side,
    # even if the "app" declares it in build_context_activated, because it only works for direct
    # dependencies. tool_requires(..., visible=True) only affects at the moment and version conflict
    # detection
    c = TestClient()
    c.save({"tool/conanfile.py": GenConanfile("tool", "0.1").with_package_type("application"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_tool_requirement("tool/0.1",
                                                                                   visible=True),
            "app/conanfile.py": GenConanfile("app", "0.1").with_requires("pkgb/0.1")
                                                          .with_settings("build_type")
                                                          .with_generator("CMakeDeps")})

    c.run("create tool")
    c.run("create pkgb")
    c.run("install app")
    cmake = c.load("app/pkgb-release-data.cmake")
    # pkgb doesn't deepnd on tool, because it is a tool-require and not build-context activated
    assert "list(APPEND pkgb_FIND_DEPENDENCY_NAMES )" in cmake
