import os
import platform
import textwrap

import pytest

from conan.tools.env.environment import environment_wrap_command
from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.sources import gen_function_cpp


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
@pytest.mark.tool("cmake")
def test_transitive_headers_not_public(transitive_libraries):
    c = transitive_libraries

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
def test_shared_requires_static(transitive_libraries):
    c = transitive_libraries

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
def test_transitive_binary_skipped(transitive_libraries):
    c = transitive_libraries
    # IMPORTANT: liba binary can be removed, no longer necessary
    c.run("remove liba*:* -c")

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


@pytest.mark.tool("cmake")
def test_shared_requires_static_build_all(transitive_libraries):
    c = transitive_libraries

    conanfile = textwrap.dedent("""\
       from conan import ConanFile

       class Pkg(ConanFile):
           requires = "libb/0.1"
           settings = "os", "compiler", "arch", "build_type"
           generators = "CMakeDeps"
        """)

    c.save({"conanfile.py": conanfile}, clean_first=True)

    arch = c.get_default_host_profile().settings['arch']

    c.run("install . -o libb*:shared=True")
    assert not os.path.exists(os.path.join(c.current_folder, f"liba-release-{arch}-data.cmake"))
    cmake = c.load(f"libb-release-{arch}-data.cmake")
    assert 'set(libb_FIND_DEPENDENCY_NAMES "")' in cmake

    c.run("install . -o libb*:shared=True --build=libb*")
    assert not os.path.exists(os.path.join(c.current_folder, f"liba-release-{arch}-data.cmake"))
    cmake = c.load(f"libb-release-{arch}-data.cmake")
    assert 'set(libb_FIND_DEPENDENCY_NAMES "")' in cmake
