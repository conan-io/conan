import os
import platform
import textwrap
import unittest

import pytest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.genconanfile import GenConanfile
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


@pytest.mark.skip(reason="CMakeDeps build modules is ongoing effort")
@pytest.mark.tool_cmake
class TestCMakeDepsGenerator:

    @pytest.mark.parametrize("use_components", [False, True])
    def test_build_modules_alias_target(self, use_components):
        client = TestClient()
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "hello"
                version = "1.0"
                settings = "os", "arch", "compiler", "build_type"
                exports_sources = ["target-alias.cmake"]
                generators = "cmake"

                def package(self):
                    self.copy("target-alias.cmake", dst="share/cmake")

                def package_info(self):
                    module = os.path.join("share", "cmake", "target-alias.cmake")
            %s
            """)
        if use_components:
            info = textwrap.dedent("""\
                self.cpp_info.name = "namespace"
                self.cpp_info.filenames["CMakeDeps"] = "hello"
                self.cpp_info.components["comp"].libs = ["hello"]
                self.cpp_info.components["comp"].build_modules["CMakeDeps"].append(module)
                """)
        else:
            info = textwrap.dedent("""\
                self.cpp_info.libs = ["hello"]
                self.cpp_info.build_modules["CMakeDeps"].append(module)
                """)
        target_alias = textwrap.dedent("""
            add_library(otherhello INTERFACE IMPORTED)
            target_link_libraries(otherhello INTERFACE {target_name})
            """).format(target_name="namespace::comp" if use_components else "hello::hello")
        conanfile = conanfile % "\n".join(["        %s" % line for line in info.splitlines()])
        client.save({"conanfile.py": conanfile, "target-alias.cmake": target_alias})
        client.run("create .")

        consumer = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "consumer"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = ["CMakeLists.txt"]
                generators = "CMakeDeps"
                requires = "hello/1.0"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
            """)
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(test)
            find_package(hello)
            get_target_property(tmp otherhello INTERFACE_LINK_LIBRARIES)
            message("otherhello link libraries: ${tmp}")
            """)
        client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
        client.run("create .")
        if use_components:
            assert "otherhello link libraries: namespace::comp" in client.out
        else:
            assert "otherhello link libraries: hello::hello" in client.out


@pytest.mark.slow
@pytest.mark.tool_cmake
class CMakeFindPathMultiGeneratorTest(unittest.TestCase):

    def test_build_modules(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "test"
                version = "1.0"
                exports_sources = ["my-module.cmake", "FindFindModule.cmake"]

                def package(self):
                    self.copy("*.cmake", dst="share/cmake")

                def package_info(self):
                    # Only first module is defined
                    # (the other one should be found by CMAKE_MODULE_PATH in builddirs)
                    builddir = os.path.join("share", "cmake")
                    module = os.path.join(builddir, "my-module.cmake")
                    self.cpp_info.build_modules.append(module)
                    self.cpp_info.builddirs = [builddir]
        """)
        # This is a module that has other find_package() calls
        my_module = textwrap.dedent("""
            find_package(FindModule REQUIRED)
            """)
        # This is a module that defines some functionality
        find_module = textwrap.dedent("""
            function(conan_message MESSAGE_OUTPUT)
                message(${ARGV${0}})
            endfunction()
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile, "my-module.cmake": my_module,
                     "FindFindModule.cmake": find_module})
        client.run("create .")
        ref = ConanFileReference("test", "1.0", None, None)
        pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID, None)
        package_path = client.cache.package_layout(ref).package(pref)
        modules_path = os.path.join(package_path, "share", "cmake")
        self.assertEqual(set(os.listdir(modules_path)),
                         {"FindFindModule.cmake", "my-module.cmake"})
        consumer = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "consumer"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = ["CMakeLists.txt"]
                generators = "CMakeDeps"
                requires = "test/1.0"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
            """)
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(test)
            find_package(test)
            conan_message("Printing using a external module!")
            """)
        client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
        client.run("create .")
        self.assertIn("Printing using a external module!", client.out)


@pytest.mark.skip(reason="CMakeDeps build modules is ongoing effort")
@pytest.mark.tool_cmake
class TestNoNamespaceTarget:
    """ This test case uses build-modules feature to create a target without a namespace. This
        target uses targets create by Conan (build_modules are included after Conan targets)
    """

    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake

        class Recipe(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = ["src/*", "build-module.cmake"]
            generators = "cmake"

            def build(self):
                cmake = CMake(self)
                cmake.configure(source_folder="src")
                cmake.build()

            def package(self):
                self.copy("*.h", dst="include", src="src")
                self.copy("*.lib", dst="lib", keep_path=False)
                self.copy("*.dll", dst="bin", keep_path=False)
                self.copy("*.dylib*", dst="lib", keep_path=False)
                self.copy("*.so", dst="lib", keep_path=False)
                self.copy("*.a", dst="lib", keep_path=False)
                self.copy("build-module.cmake", dst="share/cmake")

            def package_info(self):
                self.cpp_info.libs = ["library"]
                module = os.path.join("share", "cmake", "build-module.cmake")
                self.cpp_info.build_modules['cmake_find_package'] = [module, ]
                self.cpp_info.build_modules['CMakeDeps'] = [module, ]
    """)

    build_module = textwrap.dedent("""
        message(">> Build-module is included")

        if(NOT TARGET nonamespace)
            add_library(nonamespace INTERFACE IMPORTED)
            target_link_libraries(nonamespace INTERFACE library::library)
        endif()
    """)

    consumer = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.0)
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        project(consumer)

        find_package(library)

        get_target_property(LIBS1 library::library INTERFACE_LINK_LIBRARIES)
        message(">> library::library libs: ${LIBS1}")

        get_target_property(LIBS2 nonamespace INTERFACE_LINK_LIBRARIES)
        message(">> nonamespace libs: ${LIBS2}")

        add_executable(consumer main.cpp)
        target_link_libraries(consumer nonamespace)
    """)

    main = textwrap.dedent("""
        #include "library.h"

        int main() {
            library();
        }
    """)

    @classmethod
    def setup_class(cls):
        cls.t = t = TestClient()
        # Create a library providing a build-module
        t.run('new library/version -s')
        t.save({'conanfile.py': cls.conanfile,
                'build-module.cmake': cls.build_module})
        t.run('create conanfile.py library/version@ -s build_type=Debug')
        t.run('create conanfile.py library/version@ -s build_type=Release')
        # Prepare project to consume the targets
        t.save({'CMakeLists.txt': cls.consumer, 'main.cpp': cls.main}, clean_first=True)

    @pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
    @pytest.mark.tool_visual_studio
    def test_multi_generator_windows(self):
        t = self.t
        with t.chdir('multi_windows'):
            t.run('install library/version@ -g CMakeDeps -s build_type=Release')
            t.run('install library/version@ -g CMakeDeps -s build_type=Debug')
            generator = '-G "Visual Studio 15 Win64"'
            t.run_command(
                'cmake .. {} -DCMAKE_PREFIX_PATH:PATH="{}"'.format(generator, t.current_folder))
            assert str(t.out).count('>> Build-module is included') == 2  # FIXME: Known bug
            assert '>> nonamespace libs: library::library' in t.out
            t.run_command('cmake --build . --config Release')  # Compiles and links.

    @pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Macos")
    @pytest.mark.tool_xcode
    @pytest.mark.tool_cmake(version="3.19")
    def test_multi_generator_macos(self):
        t = self.t
        with t.chdir('multi_macos'):
            t.run('install library/version@ -g CMakeDeps -s build_type=Release')
            t.run('install library/version@ -g CMakeDeps -s build_type=Debug')
            t.run_command('cmake .. -G Xcode -DCMAKE_PREFIX_PATH:PATH="{}"'.format(t.current_folder))
            assert str(t.out).count('>> Build-module is included') == 2  # FIXME: Known bug
            assert '>> nonamespace libs: library::library' in t.out
            t.run_command('cmake --build . --config Release')  # Compiles and links.


def test_targets_declared_in_build_modules():
    """If a require is declaring the component targets in a build_module, CMakeDeps is
       fine with it, not needed to locate it as a conan declared component"""

    client = TestClient()
    conanfile_hello = str(GenConanfile().with_name("hello").with_version("1.0")
                          .with_exports_sources("*.cmake", "*.h"))
    conanfile_hello += """
    def package(self):
        self.copy("*.h", dst="include")
        self.copy("*.cmake", dst="cmake")

    def package_info(self):
        self.cpp_info.set_property("cmake_build_modules", ["cmake/my_modules.cmake"])
    """
    my_modules = textwrap.dedent("""
    add_library(cool_component INTERFACE)
    target_include_directories(cool_component INTERFACE ${CMAKE_CURRENT_LIST_DIR}/../include/)
    add_library(hello::invented ALIAS cool_component)
    """)
    hello_h = "int cool_header_only=1;"
    client.save({"conanfile.py": conanfile_hello,
                 "my_modules.cmake": my_modules, "hello.h": hello_h})
    client.run("create .")

    conanfile = GenConanfile().with_cmake_build().with_requires("hello/1.0")\
        .with_exports_sources("*.txt", "*.cpp").with_name("app").with_version("1.0")
    main_cpp = textwrap.dedent("""
        #include <iostream>
        #include "hello.h"

        int main(){
            std::cout << "cool header value: " << cool_header_only;
            return 0;
        }
        """)

    cmakelist = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        set(CMAKE_C_COMPILER_WORKS 1)
        set(CMAKE_C_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(project CXX)

        find_package(hello COMPONENTS invented)
        add_executable(myapp main.cpp)
        target_link_libraries(myapp hello::invented)
    """)
    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": cmakelist, "main.cpp": main_cpp})
    client.run("create .")
    assert "Conan: Including build module" in client.out
    assert "my_modules.cmake" in client.out
    assert "Conan: Component 'invented' found in package 'hello'" in client.out
