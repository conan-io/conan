import platform
import textwrap

import pytest

from conan.tools.env.environment import environment_wrap_command
from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.pkg_cmake import pkg_cmake
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
@pytest.mark.tool("cmake")
def test_transitive_headers_not_public():
    c = TestClient()

    c.save(pkg_cmake("liba", "0.1"))
    c.run("create .")
    c.save(pkg_cmake("libb", "0.1", requires=["liba/0.1"]), clean_first=True)
    c.run("create .")

    conanfile = textwrap.dedent("""\
       from conan import ConanFile
       from conan.tools.cmake import CMake
       class Pkg(ConanFile):
           exports = "*"
           requires = "libb/0.1"
           settings = "os", "compiler", "arch", "build_type"
           generators = "CMakeToolchain", "CMakeDeps"

           def layout(self):
               self.folders.source = "src"

           def build(self):
               cmake = CMake(self)
               cmake.configure()
               cmake.build()
        """)
    cmake = gen_cmakelists(appsources=["main.cpp"], find_package=["libb"])
    main = gen_function_cpp(name="main", includes=["libb"], calls=["libb"])
    c.save({"src/main.cpp": main,
            "src/CMakeLists.txt": cmake,
            "conanfile.py": conanfile}, clean_first=True)

    c.run("build .")
    c.run_command(".\\Release\\myapp.exe")
    assert "liba: Release!" in c.out

    # If we try to include transitivity liba headers, it will fail!!
    main = gen_function_cpp(name="main", includes=["libb", "liba"], calls=["libb"])
    c.save({"src/main.cpp": main})
    c.run("build .", assert_error=True)
    assert "Conan: Target declared 'liba::liba'" in c.out
    assert "Cannot open include file: 'liba.h'" in c.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
@pytest.mark.tool("cmake")
def test_shared_requires_static():
    c = TestClient()

    c.save(pkg_cmake("liba", "0.1"))
    c.run("create .")
    c.save(pkg_cmake("libb", "0.1", requires=["liba/0.1"]), clean_first=True)
    c.run("create . -o libb/*:shared=True")

    conanfile = textwrap.dedent("""\
       from conan import ConanFile
       from conan.tools.cmake import CMake
       class Pkg(ConanFile):
           exports = "*"
           requires = "libb/0.1"
           default_options = {"libb/*:shared": True}
           settings = "os", "compiler", "arch", "build_type"
           generators = "CMakeToolchain", "CMakeDeps", "VirtualBuildEnv", "VirtualRunEnv"

           def layout(self):
               self.folders.source = "src"

           def build(self):
               cmake = CMake(self)
               cmake.configure()
               cmake.build()
        """)
    cmake = gen_cmakelists(appsources=["main.cpp"], find_package=["libb"])
    main = gen_function_cpp(name="main", includes=["libb"], calls=["libb"])
    c.save({"src/main.cpp": main,
            "src/CMakeLists.txt": cmake,
            "conanfile.py": conanfile}, clean_first=True)

    c.run("build .")
    command = environment_wrap_command("conanrun", c.current_folder, ".\\Release\\myapp.exe")
    c.run_command(command)
    assert "liba: Release!" in c.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
@pytest.mark.tool("cmake")
def test_transitive_binary_skipped():
    c = TestClient()

    c.save(pkg_cmake("liba", "0.1"))
    c.run("create .")
    c.save(pkg_cmake("libb", "0.1", requires=["liba/0.1"]), clean_first=True)
    c.run("create . -o libb/*:shared=True")
    # IMPORTANT: liba binary can be removed, no longer necessary
    c.run("remove liba* -p -f")

    conanfile = textwrap.dedent("""\
       from conan import ConanFile
       from conan.tools.cmake import CMake
       class Pkg(ConanFile):
           exports = "*"
           requires = "libb/0.1"
           default_options = {"libb/*:shared": True}
           settings = "os", "compiler", "arch", "build_type"
           generators = "CMakeToolchain", "CMakeDeps"

           def layout(self):
               self.folders.source = "src"

           def build(self):
               cmake = CMake(self)
               cmake.configure()
               cmake.build()
        """)
    cmake = gen_cmakelists(appsources=["main.cpp"], find_package=["libb"])
    main = gen_function_cpp(name="main", includes=["libb"], calls=["libb"])
    c.save({"src/main.cpp": main,
            "src/CMakeLists.txt": cmake,
            "conanfile.py": conanfile}, clean_first=True)

    c.run("build . ")
    command = environment_wrap_command("conanrun", c.current_folder, ".\\Release\\myapp.exe")
    c.run_command(command)
    assert "liba: Release!" in c.out

    # If we try to include transitivity liba headers, it will fail!!
    main = gen_function_cpp(name="main", includes=["libb", "liba"], calls=["libb"])
    c.save({"src/main.cpp": main})
    c.run("build .", assert_error=True)
    assert "Cannot open include file: 'liba.h'" in c.out
