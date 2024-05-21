import os
import platform
import textwrap
import time
import unittest

import pytest
from parameterized.parameterized import parameterized

from conan.test.assets.cmake import gen_cmakelists
from conan.test.assets.sources import gen_function_cpp, gen_function_h
from test.functional.utils import check_vs_runtime, check_exe_run
from conan.test.utils.tools import TestClient
from conans.util.files import save


@pytest.mark.tool("cmake", "3.15")
@pytest.mark.tool("mingw64")
@pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows")
def test_simple_cmake_mingw():
    client = TestClient()
    client.run("new cmake_lib -d name=hello -d version=1.0")
    client.save({"mingw": """
        [settings]
        os=Windows
        arch=x86_64
        build_type=Release
        compiler=gcc
        compiler.exception=seh
        compiler.libcxx=libstdc++11
        compiler.threads=win32
        compiler.version=11.2
        compiler.cppstd=17
        """})
    client.run("create . --profile=mingw")
    build_folder = client.created_test_build_folder("hello/1.0")
    # FIXME: Note that CI contains 10.X, so it uses another version rather than the profile one
    #  and no one notices. It would be good to have some details in confuser.py to be consistent
    check_exe_run(client.out, "hello/1.0:", "gcc", None, "Release", "x86_64", "17",
                  subsystem="mingw64", extra_msg="Hello World", cxx11_abi="1")
    check_vs_runtime(f"test_package/{build_folder}/example.exe", client, "15",
                     build_type="Release", static_runtime=False, subsystem="mingw64")

# TODO: How to link with mingw statically?


@pytest.mark.tool("cmake")
class Base(unittest.TestCase):

    conanfile = textwrap.dedent(r"""
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain
        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/0.1"
            generators = "CMakeDeps"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}
            implements = ["auto_shared_fpic", "auto_header_only"]

            def generate(self):
                tc = CMakeToolchain(self)
                tc.variables["MYVAR"] = "MYVAR_VALUE"
                tc.variables["MYVAR2"] = "MYVAR_VALUE2"
                tc.variables.debug["MYVAR_CONFIG"] = "MYVAR_DEBUG"
                tc.variables.release["MYVAR_CONFIG"] = "MYVAR_RELEASE"
                tc.variables.debug["MYVAR2_CONFIG"] = "MYVAR2_DEBUG"
                tc.variables.release["MYVAR2_CONFIG"] = "MYVAR2_RELEASE"
                tc.preprocessor_definitions["MYDEFINE"] = "\"MYDEF_VALUE\""
                tc.preprocessor_definitions["MYDEFINEINT"] = 42
                tc.preprocessor_definitions.debug["MYDEFINE_CONFIG"] = "\"MYDEF_DEBUG\""
                tc.preprocessor_definitions.release["MYDEFINE_CONFIG"] = "\"MYDEF_RELEASE\""
                tc.preprocessor_definitions.debug["MYDEFINEINT_CONFIG"] = 421
                tc.preprocessor_definitions.release["MYDEFINEINT_CONFIG"] = 422
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        """)

    lib_h = gen_function_h(name="app")
    lib_cpp = gen_function_cpp(name="app", msg="App", includes=["hello"], calls=["hello"],
                               preprocessor=["MYVAR", "MYVAR_CONFIG", "MYDEFINE", "MYDEFINE_CONFIG",
                                             "MYDEFINEINT", "MYDEFINEINT_CONFIG"])
    main = gen_function_cpp(name="main", includes=["app"], calls=["app"])

    cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(App C CXX)

        if(NOT CMAKE_TOOLCHAIN_FILE)
            message(FATAL ">> Not using toolchain")
        endif()
        message(">> CMAKE_GENERATOR_PLATFORM: ${CMAKE_GENERATOR_PLATFORM}")
        message(">> CMAKE_BUILD_TYPE: ${CMAKE_BUILD_TYPE}")
        message(">> CMAKE_CXX_FLAGS: ${CMAKE_CXX_FLAGS}")
        message(">> CMAKE_CXX_FLAGS_DEBUG: ${CMAKE_CXX_FLAGS_DEBUG}")
        message(">> CMAKE_CXX_FLAGS_RELEASE: ${CMAKE_CXX_FLAGS_RELEASE}")
        message(">> CMAKE_C_FLAGS: ${CMAKE_C_FLAGS}")
        message(">> CMAKE_C_FLAGS_DEBUG: ${CMAKE_C_FLAGS_DEBUG}")
        message(">> CMAKE_C_FLAGS_RELEASE: ${CMAKE_C_FLAGS_RELEASE}")
        message(">> CMAKE_SHARED_LINKER_FLAGS: ${CMAKE_SHARED_LINKER_FLAGS}")
        message(">> CMAKE_EXE_LINKER_FLAGS: ${CMAKE_EXE_LINKER_FLAGS}")
        message(">> CMAKE_CXX_STANDARD: ${CMAKE_CXX_STANDARD}")
        message(">> CMAKE_CXX_EXTENSIONS: ${CMAKE_CXX_EXTENSIONS}")
        message(">> CMAKE_POSITION_INDEPENDENT_CODE: ${CMAKE_POSITION_INDEPENDENT_CODE}")
        message(">> CMAKE_SKIP_RPATH: ${CMAKE_SKIP_RPATH}")
        message(">> CMAKE_INSTALL_NAME_DIR: ${CMAKE_INSTALL_NAME_DIR}")
        message(">> CMAKE_MODULE_PATH: ${CMAKE_MODULE_PATH}")
        message(">> CMAKE_PREFIX_PATH: ${CMAKE_PREFIX_PATH}")
        message(">> BUILD_SHARED_LIBS: ${BUILD_SHARED_LIBS}")
        get_directory_property(_COMPILE_DEFS DIRECTORY ${CMAKE_SOURCE_DIR} COMPILE_DEFINITIONS)
        message(">> COMPILE_DEFINITIONS: ${_COMPILE_DEFS}")

        find_package(hello REQUIRED)
        add_library(app_lib app_lib.cpp)
        target_link_libraries(app_lib PRIVATE hello::hello)
        target_compile_definitions(app_lib PRIVATE MYVAR="${MYVAR}")
        target_compile_definitions(app_lib PRIVATE MYVAR_CONFIG="${MYVAR_CONFIG}")
        add_executable(app app.cpp)
        target_link_libraries(app PRIVATE app_lib)
        """)

    def setUp(self):
        self.client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import save
            import os
            class Pkg(ConanFile):
                settings = "build_type"
                def package(self):
                    save(self, os.path.join(self.package_folder, "include/hello.h"),
                         '''#include <iostream>
                         void hello(){std::cout<< "Hello: %s" <<std::endl;}'''
                         % self.settings.build_type)
            """)
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . --name=hello --version=0.1 -s build_type=Debug")
        self.client.run("create . --name=hello --version=0.1 -s build_type=Release")

        # Prepare the actual consumer package
        self.client.save({"conanfile.py": self.conanfile,
                          "CMakeLists.txt": self.cmakelist,
                          "app.cpp": self.main,
                          "app_lib.cpp": self.lib_cpp,
                          "app.h": self.lib_h})

    def _run_build(self, settings=None, options=None):
        # Build the profile according to the settings provided
        settings = settings or {}
        settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)
        options = " ".join("-o %s=%s" % (k, v) for k, v in options.items()) if options else ""

        # Run the configure corresponding to this test case
        build_directory = os.path.join(self.client.current_folder, "build").replace("\\", "/")
        with self.client.chdir(build_directory):
            self.client.run("build .. %s %s -of=." % (settings, options))
            install_out = self.client.out
        return install_out

    def _modify_code(self):
        lib_cpp = gen_function_cpp(name="app", msg="AppImproved", includes=["hello"],
                                   calls=["hello"], preprocessor=["MYVAR", "MYVAR_CONFIG",
                                                                  "MYDEFINE", "MYDEFINE_CONFIG",
                                                                  "MYDEFINEINT",
                                                                  "MYDEFINEINT_CONFIG"])
        self.client.save({"app_lib.cpp": lib_cpp})

        content = self.client.load("CMakeLists.txt")
        content = content.replace(">>", "++>>")
        self.client.save({"CMakeLists.txt": content})

    def _incremental_build(self, build_type=None):
        build_directory = os.path.join(self.client.current_folder, "build").replace("\\", "/")
        with self.client.chdir(build_directory):
            config = "--config %s" % build_type if build_type else ""
            self.client.run_command("cmake --build . %s" % config)

    def _run_app(self, build_type, bin_folder=False, msg="App", dyld_path=None):
        if dyld_path:
            build_directory = os.path.join(self.client.current_folder, "build").replace("\\", "/")
            command_str = 'DYLD_LIBRARY_PATH="%s" build/app' % build_directory
        else:
            command_str = "build/%s/app.exe" % build_type if bin_folder else "build/app"
            if platform.system() == "Windows":
                command_str = command_str.replace("/", "\\")
        self.client.run_command(command_str)
        self.assertIn("Hello: %s" % build_type, self.client.out)
        self.assertIn("%s: %s!" % (msg, build_type), self.client.out)
        self.assertIn("MYVAR: MYVAR_VALUE", self.client.out)
        self.assertIn("MYVAR_CONFIG: MYVAR_%s" % build_type.upper(), self.client.out)
        self.assertIn("MYDEFINE: MYDEF_VALUE", self.client.out)
        self.assertIn("MYDEFINE_CONFIG: MYDEF_%s" % build_type.upper(), self.client.out)
        self.assertIn("MYDEFINEINT: 42", self.client.out)
        self.assertIn("MYDEFINEINT_CONFIG: {}".format(421 if build_type == "Debug" else 422),
                      self.client.out)


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
class WinTest(Base):
    @parameterized.expand([("msvc", "Debug", "static", "191", "14", "x86", None, True),
                           ("msvc", "Release", "dynamic", "191", "17", "x86_64", None, False)]
                          )
    def test_toolchain_win(self, compiler, build_type, runtime, version, cppstd, arch, toolset,
                           shared):
        settings = {"compiler": compiler,
                    "compiler.version": version,
                    "compiler.toolset": toolset,
                    "compiler.runtime": runtime,
                    "compiler.cppstd": cppstd,
                    "arch": arch,
                    "build_type": build_type,
                    }
        options = {"shared": shared}
        save(self.client.cache.new_config_path, "tools.build:jobs=1")
        self._run_build(settings, options)
        self.assertIn('cmake -G "Visual Studio 15 2017" '
                      '-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"', self.client.out)
        if toolset == "v140":
            self.assertIn("Microsoft Visual Studio 14.0", self.client.out)
        else:
            self.assertIn("Microsoft Visual Studio/2017", self.client.out)

        generator_platform = "x64" if arch == "x86_64" else "Win32"
        arch_flag = "x64" if arch == "x86_64" else "X86"
        shared_str = "ON" if shared else "OFF"
        vals = {"CMAKE_GENERATOR_PLATFORM": generator_platform,
                "CMAKE_BUILD_TYPE": "",
                "CMAKE_CXX_FLAGS": "/MP1 /DWIN32 /D_WINDOWS /GR /EHsc",
                "CMAKE_CXX_FLAGS_DEBUG": "/Zi /Ob0 /Od /RTC1",
                "CMAKE_CXX_FLAGS_RELEASE": "/O2 /Ob2 /DNDEBUG",
                "CMAKE_C_FLAGS": "/MP1 /DWIN32 /D_WINDOWS",
                "CMAKE_C_FLAGS_DEBUG": "/Zi /Ob0 /Od /RTC1",
                "CMAKE_C_FLAGS_RELEASE": "/O2 /Ob2 /DNDEBUG",
                "CMAKE_SHARED_LINKER_FLAGS": "/machine:%s" % arch_flag,
                "CMAKE_EXE_LINKER_FLAGS": "/machine:%s" % arch_flag,
                "CMAKE_CXX_STANDARD": cppstd,
                "CMAKE_CXX_EXTENSIONS": "OFF",
                "BUILD_SHARED_LIBS": shared_str}

        def _verify_out(marker=">>"):
            if shared:
                self.assertIn("app_lib.dll", self.client.out)
            else:
                self.assertNotIn("app_lib.dll", self.client.out)

            out = str(self.client.out).splitlines()
            for k, v in vals.items():
                self.assertIn("%s %s: %s" % (marker, k, v), out)

        _verify_out()

        opposite_build_type = "Release" if build_type == "Debug" else "Debug"
        settings["build_type"] = opposite_build_type
        if runtime == "MTd":
            settings["compiler.runtime"] = "MT"
        if runtime == "MD":
            settings["compiler.runtime"] = "MDd"
        self._run_build(settings, options)

        self._run_app("Release", bin_folder=True)
        if compiler == "msvc":
            visual_version = version
        else:
            visual_version = "190" if toolset == "v140" else "191"
        check_exe_run(self.client.out, "main", "msvc", visual_version, "Release", arch, cppstd,
                      {"MYVAR": "MYVAR_VALUE",
                       "MYVAR_CONFIG": "MYVAR_RELEASE",
                       "MYDEFINE": "MYDEF_VALUE",
                       "MYDEFINE_CONFIG": "MYDEF_RELEASE"
                       })
        self._run_app("Debug", bin_folder=True)
        check_exe_run(self.client.out, "main", "msvc", visual_version, "Debug", arch, cppstd,
                      {"MYVAR": "MYVAR_VALUE",
                       "MYVAR_CONFIG": "MYVAR_DEBUG",
                       "MYDEFINE": "MYDEF_VALUE",
                       "MYDEFINE_CONFIG": "MYDEF_DEBUG"
                       })

        static_runtime = True if runtime == "static" or "MT" in runtime else False
        check_vs_runtime("build/Release/app.exe", self.client, "15", build_type="Release",
                         static_runtime=static_runtime)
        check_vs_runtime("build/Debug/app.exe", self.client, "15", build_type="Debug",
                         static_runtime=static_runtime)

        self._modify_code()
        time.sleep(1)
        self._incremental_build(build_type=build_type)
        _verify_out(marker="++>>")
        self._run_app(build_type, bin_folder=True, msg="AppImproved")
        self._incremental_build(build_type=opposite_build_type)
        self._run_app(opposite_build_type, bin_folder=True, msg="AppImproved")

    @parameterized.expand([("Debug", "libstdc++", "4.9", "98", "x86_64", True),
                           ("Release", "libstdc++", "4.9", "11", "x86_64", False)])
    @pytest.mark.tool("mingw64")
    @pytest.mark.tool("cmake", "3.15")
    def test_toolchain_mingw_win(self, build_type, libcxx, version, cppstd, arch, shared):
        # FIXME: The version and cppstd are wrong, toolchain doesn't enforce it
        settings = {"compiler": "gcc",
                    "compiler.version": version,
                    "compiler.libcxx": libcxx,
                    "compiler.cppstd": cppstd,
                    "arch": arch,
                    "build_type": build_type,
                    }
        options = {"shared": shared}
        self._run_build(settings, options)
        self.assertIn("The C compiler identification is GNU", self.client.out)
        self.assertIn('cmake -G "MinGW Makefiles" '
                      '-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"', self.client.out)
        assert '-DCMAKE_SH="CMAKE_SH-NOTFOUND"' in self.client.out

        def _verify_out(marker=">>"):
            cmake_vars = {"CMAKE_GENERATOR_PLATFORM": "",
                          "CMAKE_BUILD_TYPE": build_type,
                          "CMAKE_CXX_FLAGS": "-m64",
                          "CMAKE_CXX_FLAGS_DEBUG": "-g",
                          "CMAKE_CXX_FLAGS_RELEASE": "-O3 -DNDEBUG",
                          "CMAKE_C_FLAGS": "-m64",
                          "CMAKE_C_FLAGS_DEBUG": "-g",
                          "CMAKE_C_FLAGS_RELEASE": "-O3 -DNDEBUG",
                          "CMAKE_SHARED_LINKER_FLAGS": "-m64",
                          "CMAKE_EXE_LINKER_FLAGS": "-m64",
                          "CMAKE_CXX_STANDARD": cppstd,
                          "CMAKE_CXX_EXTENSIONS": "OFF",
                          "BUILD_SHARED_LIBS": "ON" if shared else "OFF"}
            if shared:
                self.assertIn("app_lib.dll", self.client.out)
            else:
                self.assertNotIn("app_lib.dll", self.client.out)

            out = str(self.client.out).splitlines()
            for k, v in cmake_vars.items():
                self.assertIn("%s %s: %s" % (marker, k, v), out)

        _verify_out()
        self._run_app(build_type)
        check_exe_run(self.client.out, "main", "gcc", None, build_type, arch, None,
                      {"MYVAR": "MYVAR_VALUE",
                       "MYVAR_CONFIG": "MYVAR_{}".format(build_type.upper()),
                       "MYDEFINE": "MYDEF_VALUE",
                       "MYDEFINE_CONFIG": "MYDEF_{}".format(build_type.upper())
                       }, subsystem="mingw64")

        self._modify_code()
        time.sleep(2)
        self._incremental_build()
        _verify_out(marker="++>>")
        self._run_app(build_type, msg="AppImproved")


@pytest.mark.skipif(platform.system() != "Linux", reason="Only for Linux")
class LinuxTest(Base):
    @parameterized.expand([("Debug",  "14", "x86", "libstdc++", True),
                           ("Release", "gnu14", "x86_64", "libstdc++11", False)])
    def test_toolchain_linux(self, build_type, cppstd, arch, libcxx, shared):
        settings = {"compiler": "gcc",
                    "compiler.cppstd": cppstd,
                    "compiler.libcxx": libcxx,
                    "arch": arch,
                    "build_type": build_type}
        self._run_build(settings, {"shared": shared})
        self.assertIn('cmake -G "Unix Makefiles" '
                      '-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"', self.client.out)

        extensions_str = "ON" if "gnu" in cppstd else "OFF"
        arch_str = "-m32" if arch == "x86" else "-m64"
        cxx11_abi_str = "_GLIBCXX_USE_CXX11_ABI=0;" if libcxx == "libstdc++" else ""
        defines = '%sMYDEFINE="MYDEF_VALUE";MYDEFINEINT=42;' \
                  '$<$<CONFIG:debug>:MYDEFINE_CONFIG="MYDEF_DEBUG">' \
                  '$<$<CONFIG:release>:MYDEFINE_CONFIG="MYDEF_RELEASE">;' \
                  '$<$<CONFIG:debug>:MYDEFINEINT_CONFIG=421>' \
                  '$<$<CONFIG:release>:MYDEFINEINT_CONFIG=422>' % cxx11_abi_str
        vals = {"CMAKE_CXX_STANDARD": "14",
                "CMAKE_CXX_EXTENSIONS": extensions_str,
                "CMAKE_BUILD_TYPE": build_type,
                "CMAKE_CXX_FLAGS": arch_str,
                "CMAKE_CXX_FLAGS_DEBUG": "-g",
                "CMAKE_CXX_FLAGS_RELEASE": "-O3 -DNDEBUG",
                "CMAKE_C_FLAGS": arch_str,
                "CMAKE_C_FLAGS_DEBUG": "-g",
                "CMAKE_C_FLAGS_RELEASE": "-O3 -DNDEBUG",
                "CMAKE_SHARED_LINKER_FLAGS": arch_str,
                "CMAKE_EXE_LINKER_FLAGS": arch_str,
                "COMPILE_DEFINITIONS": defines,
                # fPIC is managed automatically depending on the shared option value
                # if implements = ["auto_shared_fpic", "auto_header_only"]
                "CMAKE_POSITION_INDEPENDENT_CODE": "ON" if not shared else ""
                }

        def _verify_out(marker=">>"):
            if shared:
                self.assertIn("libapp_lib.so", self.client.out)
            else:
                self.assertIn("libapp_lib.a", self.client.out)

            out = str(self.client.out).splitlines()
            for k, v in vals.items():
                self.assertIn("%s %s: %s" % (marker, k, v), out)

        _verify_out()

        self._run_app(build_type)

        self._modify_code()
        self._incremental_build()
        _verify_out(marker="++>>")
        self._run_app(build_type, msg="AppImproved")


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for Apple")
class AppleTest(Base):
    @parameterized.expand([("Debug",  "14",  True),
                           ("Release", "", False)])
    def test_toolchain_apple(self, build_type, cppstd, shared):
        settings = {"compiler": "apple-clang",
                    "compiler.cppstd": cppstd,
                    "build_type": build_type}
        self._run_build(settings, {"shared": shared})

        self.assertIn('cmake -G "Unix Makefiles" '
                      '-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"', self.client.out)

        extensions_str = "OFF" if cppstd else ""
        vals = {"CMAKE_CXX_STANDARD": cppstd,
                "CMAKE_CXX_EXTENSIONS": extensions_str,
                "CMAKE_BUILD_TYPE": build_type,
                "CMAKE_CXX_FLAGS_DEBUG": "-g",
                "CMAKE_CXX_FLAGS_RELEASE": "-O3 -DNDEBUG",
                "CMAKE_C_FLAGS_DEBUG": "-g",
                "CMAKE_C_FLAGS_RELEASE": "-O3 -DNDEBUG",
                "CMAKE_INSTALL_NAME_DIR": ""
                }

        host_profile = self.client.get_default_host_profile()
        if host_profile.settings.get("arch") == "x86_64":
            vals.update({
                "CMAKE_C_FLAGS": "-m64",
                "CMAKE_CXX_FLAGS": "-m64 -stdlib=libc++",
                "CMAKE_SHARED_LINKER_FLAGS": "-m64",
                "CMAKE_EXE_LINKER_FLAGS": "-m64",
            })
        else:
            vals.update({
                "CMAKE_CXX_FLAGS": "-stdlib=libc++",
            })

        def _verify_out(marker=">>"):
            if shared:
                self.assertIn("libapp_lib.dylib", self.client.out)
            else:
                if marker == ">>":
                    self.assertIn("libapp_lib.a", self.client.out)
                else:  # Incremental build not the same msg
                    self.assertIn("Built target app_lib", self.client.out)
            out = str(self.client.out).splitlines()
            for k, v in vals.items():
                self.assertIn("%s %s: %s" % (marker, k, v), out)

        _verify_out()

        self._run_app(build_type, dyld_path=shared)

        self._modify_code()
        time.sleep(1)
        self._incremental_build()
        _verify_out(marker="++>>")
        self._run_app(build_type, dyld_path=shared, msg="AppImproved")


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
@pytest.mark.parametrize("version, vs_version",
                         [("190", "15"),
                          ("191", "15")])
def test_msvc_vs_versiontoolset(version, vs_version):
    settings = {"compiler": "msvc",
                "compiler.version": version,
                "compiler.runtime": "static",
                "compiler.cppstd": "14",
                "arch": "x86_64",
                "build_type": "Release",
                }
    client = TestClient()
    save(client.cache.new_config_path,
         "tools.microsoft.msbuild:vs_version={}".format(vs_version))
    conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMake
            class App(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                generators = "CMakeToolchain"
                options = {"shared": [True, False], "fPIC": [True, False]}
                default_options = {"shared": False, "fPIC": True}
                exports_sources = "*"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
                    self.run("Release\\myapp.exe")
            """)
    cmakelists = gen_cmakelists(appname="myapp", appsources=["app.cpp"])
    main = gen_function_cpp(name="main")
    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": cmakelists,
                 "app.cpp": main,
                 })
    settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)
    client.run("create . --name=app --version=1.0 {}".format(settings))
    assert '-G "Visual Studio 15 2017"' in client.out

    check_exe_run(client.out, "main", "msvc", version, "Release", "x86_64", "14")


@pytest.mark.tool("cmake")
class CMakeInstallTest(unittest.TestCase):

    def test_install(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMake, CMakeToolchain
            class App(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                exports_sources = "CMakeLists.txt", "header.h"
                def generate(self):
                    tc = CMakeToolchain(self)
                    tc.generate()
                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                def package(self):
                    cmake = CMake(self)
                    cmake.install()
            """)

        cmakelist = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.8)
            project(App C)
            install(FILES header.h DESTINATION include)
            """)
        client = TestClient(path_with_spaces=False)
        client.save({"conanfile.py": conanfile,
                     "CMakeLists.txt": cmakelist,
                     "header.h": "# my header file"})

        # The create flow must work
        client.run("create . --name=pkg --version=0.1 -c tools.build:verbosity=verbose -c tools.compilation:verbosity=verbose")
        assert "--loglevel=VERBOSE" in client.out
        assert "unrecognized option" not in client.out
        assert "--verbose" in client.out
        self.assertIn("pkg/0.1: package(): Packaged 1 '.h' file: header.h", client.out)
        package_folder = client.created_layout().package()
        self.assertTrue(os.path.exists(os.path.join(package_folder, "include", "header.h")))

    def test_install_in_build(self):
        """
        test that we can do a ``cmake.install()`` inside the ``build()`` method without
        crashing
        """
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMake, CMakeToolchain
            class App(ConanFile):
                settings = "os", "arch", "compiler", "build_type"

                def generate(self):
                    tc = CMakeToolchain(self)
                    tc.generate()
                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.install()
            """)

        cmakelist = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.8)
            project(App C)
            install(FILES header.h DESTINATION include)
            """)
        client = TestClient(path_with_spaces=False)
        client.save({"conanfile.py": conanfile,
                     "CMakeLists.txt": cmakelist,
                     "header.h": "# my header file"})

        # The create flow must work
        client.run("build .")
        assert "conanfile.py: RUN: cmake --install" in client.out


@pytest.mark.tool("cmake")
class TestCmakeTestMethod:
    """
    test the cmake.test() helper
    """
    def test_test(self):

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMake
            class App(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                generators = "CMakeDeps", "CMakeToolchain", "VirtualBuildEnv", "VirtualRunEnv"
                exports_sources = "CMakeLists.txt", "example.cpp"

                def build_requirements(self):
                    self.test_requires("test/0.1")

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
                    cmake.test()
                    cmake.ctest()
            """)

        cmakelist = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(App CXX)
            find_package(test CONFIG REQUIRED)
            add_executable(example example.cpp)
            target_link_libraries(example test::test)

            enable_testing()
            add_test(NAME example
                      COMMAND example)
            """)
        c = TestClient()
        c.run("new cmake_lib -d name=test -d version=0.1")
        c.run("create .  -tf=\"\" -o test*:shared=True")

        c.save({"conanfile.py": conanfile,
                "CMakeLists.txt": cmakelist,
                "example.cpp": gen_function_cpp(name="main", includes=["test"], calls=["test"])},
               clean_first=True)

        # The create flow must work
        c.run("create . --name=pkg --version=0.1 -pr:b=default -o test*:shared=True")
        assert str(c.out).count("1/1 Test #1: example ..........................   Passed") == 2
        assert "pkg/0.1: RUN: ctest --build-config Release --parallel"


@pytest.mark.tool("cmake")
class CMakeOverrideCacheTest(unittest.TestCase):

    def test_cmake_cache_variables(self):
        # https://github.com/conan-io/conan/issues/7832
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMake, CMakeToolchain
            class App(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                exports_sources = "CMakeLists.txt"
                def generate(self):
                    toolchain = CMakeToolchain(self)
                    toolchain.variables["my_config_string"] = "my new value"
                    toolchain.generate()
                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
            """)

        cmakelist = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.7)
            project(my_project)
            set(my_config_string "default value" CACHE STRING "my config string")
            message(STATUS "VALUE OF CONFIG STRING: ${my_config_string}")
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "CMakeLists.txt": cmakelist})
        client.run("build .")
        self.assertIn("VALUE OF CONFIG STRING: my new value", client.out)


@pytest.mark.tool("cmake")
class TestCMakeFindPackagePreferConfig:

    def test_prefer_config(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMake
            class App(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                generators = "CMakeToolchain"
                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
            """)

        cmakelist = textwrap.dedent("""
            set(CMAKE_C_COMPILER_WORKS 1)
            set(CMAKE_C_ABI_COMPILED 1)
            cmake_minimum_required(VERSION 3.15)
            project(my_project C)
            find_package(Comandante REQUIRED)
            """)

        find = 'message(STATUS "using FindComandante.cmake")'
        config = 'message(STATUS "using ComandanteConfig.cmake")'

        profile = textwrap.dedent("""
            include(default)
            [conf]
            tools.cmake.cmaketoolchain:find_package_prefer_config={}
            """)

        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "CMakeLists.txt": cmakelist,
                     "FindComandante.cmake": find,
                     "ComandanteConfig.cmake": config,
                     "profile_true": profile.format(True),
                     "profile_false": profile.format(False)})

        client.run("build .")
        assert "using ComandanteConfig.cmake" in client.out

        client.run("build . --profile=profile_true")
        assert "using ComandanteConfig.cmake" in client.out

        client.run("build . --profile=profile_false")
        assert "using FindComandante.cmake" in client.out

