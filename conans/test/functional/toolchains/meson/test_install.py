import os
import textwrap

from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.functional.toolchains.meson._base import TestMesonBase


class MesonInstall(TestMesonBase):
    _conanfile_py = textwrap.dedent("""
        import os
        import shutil
        from conans import ConanFile, tools
        from conan.tools.meson import Meson, MesonToolchain


        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}
            exports_sources = "meson.build", "hello.cpp", "hello.h"

            def config_options(self):
                if self.settings.os == "Windows":
                    del self.options.fPIC

            def generate(self):
                tc = MesonToolchain(self)
                # https://mesonbuild.com/Release-notes-for-0-50-0.html#libdir-defaults-to-lib-when-cross-compiling
                tc.definitions["libdir"] = "lib"
                tc.generate()

            def build(self):
                meson = Meson(self)
                meson.configure()
                meson.build()

            def package(self):
                meson = Meson(self)
                meson.configure()
                meson.install()

                # https://mesonbuild.com/FAQ.html#why-does-building-my-project-with-msvc-output-static-libraries-called-libfooa
                if self.settings.compiler == 'Visual Studio' and not self.options.shared:
                    shutil.move(os.path.join(self.package_folder, "lib", "libhello.a"),
                                os.path.join(self.package_folder, "lib", "hello.lib"))

            def package_info(self):
                self.cpp_info.libs = ['hello']
        """)

    _meson_build = textwrap.dedent("""
        project('tutorial', 'cpp')
        library('hello', 'hello.cpp', install: true)
        install_headers('hello.h')
        """)

    _test_package_conanfile_py = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake, tools


        class TestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "cmake"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def test(self):
                if not tools.cross_building(self):
                    self.run(os.path.join("bin", "test_package"), run_environment=True)
        """)

    _test_package_cmake_lists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.1)
        project(test_package CXX)

        include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
        conan_basic_setup()

        add_executable(${PROJECT_NAME} test_package.cpp)
        target_link_libraries(${PROJECT_NAME} ${CONAN_LIBS})
        """)

    def test_install(self):
        hello_cpp = gen_function_cpp(name="hello")
        hello_h = gen_function_h(name="hello")
        test_package_cpp = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        self.t.save({"conanfile.py": self._conanfile_py,
                     "meson.build": self._meson_build,
                     "hello.cpp": hello_cpp,
                     "hello.h": hello_h,
                     os.path.join("test_package", "conanfile.py"): self._test_package_conanfile_py,
                     os.path.join("test_package", "CMakeLists.txt"): self._test_package_cmake_lists,
                     os.path.join("test_package", "test_package.cpp"): test_package_cpp})

        self.t.run("create . hello/0.1@ %s" % self._settings_str)

        self._check_binary()
