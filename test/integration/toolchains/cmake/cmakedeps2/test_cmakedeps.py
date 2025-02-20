import re
import textwrap

from conan.test.utils.tools import TestClient

new_value = "will_break_next"


def test_cmakedeps_direct_deps_paths():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan.tools.files import copy
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "lib"
            version = "1.0"
            def package_info(self):
                self.cpp_info.includedirs = ["myincludes"]
                self.cpp_info.libdirs = ["mylib"]
    """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.cmake import CMake
        class PkgConan(ConanFile):
            requires = "lib/1.0"
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeDeps"
            def build(self):
                cmake = CMake(self)
                cmake.configure()
    """)
    c.save({"conanfile.py": conanfile}, clean_first=True)
    c.run(f"install . -c tools.cmake.cmakedeps:new={new_value}")
    cmake_paths = c.load("conan_cmakedeps_paths.cmake")
    assert re.search(r"list\(PREPEND CMAKE_PROGRAM_PATH \".*/bin\"", cmake_paths)  # default
    assert re.search(r"list\(PREPEND CMAKE_LIBRARY_PATH \".*/mylib\"", cmake_paths)
    assert re.search(r"list\(PREPEND CMAKE_INCLUDE_PATH \".*/myincludes\"", cmake_paths)


def test_cmakedeps_transitive_paths():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan.tools.files import copy
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "liba"
            version = "1.0"
            def package_info(self):
                self.cpp_info.includedirs = ["includea"]
                self.cpp_info.libdirs = ["liba"]
                self.cpp_info.bindirs = ["bina"]
    """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")
    conanfile = textwrap.dedent("""
        import os
        from conan.tools.files import copy
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "libb"
            version = "1.0"
            requires = "liba/1.0"
            def package_info(self):
                self.cpp_info.includedirs = ["includeb"]
                self.cpp_info.libdirs = ["libb"]
                self.cpp_info.bindirs = ["binb"]
    """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.cmake import CMake
        class PkgConan(ConanFile):
            requires = "libb/1.0"
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeDeps"
            def build(self):
                cmake = CMake(self)
                cmake.configure()
    """)
    c.save({"conanfile.py": conanfile}, clean_first=True)
    c.run(f"install . -c tools.cmake.cmakedeps:new={new_value}")
    cmake_paths = c.load("conan_cmakedeps_paths.cmake")
    cmake_paths.replace("\\", "/")
    assert re.search(r"list\(PREPEND CMAKE_PROGRAM_PATH \".*/libb.*/p/binb\"\)", cmake_paths)
    assert not re.search(r"list\(PREPEND CMAKE_PROGRAM_PATH /bina\"", cmake_paths)
    assert re.search(r"list\(PREPEND CMAKE_LIBRARY_PATH \".*/libb.*/p/libb\" \".*/liba.*/p/liba\"\)", cmake_paths)
    assert re.search(r"list\(PREPEND CMAKE_INCLUDE_PATH \".*/libb.*/p/includeb\" \".*/liba.*/p/includea\"\)", cmake_paths)
