import json
import os
import platform
import re
import textwrap

import pytest

from conan.tools.microsoft.visual import vcvars_command
from conan.test.assets.cmake import gen_cmakelists
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save
from test.conftest import tools_locations


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
@pytest.mark.parametrize("compiler, version, update, runtime",
                         [("msvc", "192", None, "dynamic"),
                          ("msvc", "192", "6", "static"),
                          ("msvc", "192", "8", "static")])
def test_cmake_toolchain_win_toolset(compiler, version, update, runtime):
    client = TestClient(path_with_spaces=False)
    settings = {"compiler": compiler,
                "compiler.version": version,
                "compiler.update": update,
                "compiler.cppstd": "17",
                "compiler.runtime": runtime,
                "build_type": "Release",
                "arch": "x86_64"}

    # Build the profile according to the settings provided
    settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)

    conanfile = GenConanfile().with_settings("os", "compiler", "build_type", "arch").\
        with_generator("CMakeToolchain")

    client.save({"conanfile.py": conanfile})
    client.run("install . {}".format(settings))
    toolchain = client.load("conan_toolchain.cmake")
    value = "v14{}".format(version[-1])
    if update is not None:  # Fullversion
        value += f",version=14.{version[-1]}{update}"
    assert 'set(CMAKE_GENERATOR_TOOLSET "{}" CACHE STRING "" FORCE)'.format(value) in toolchain


def test_cmake_toolchain_user_toolchain():
    client = TestClient(path_with_spaces=False)
    conanfile = GenConanfile().with_settings("os", "compiler", "build_type", "arch").\
        with_generator("CMakeToolchain")
    client.save_home({"global.conf": "tools.cmake.cmaketoolchain:user_toolchain+=mytoolchain.cmake"})

    client.save({"conanfile.py": conanfile})
    client.run("install .")
    toolchain = client.load("conan_toolchain.cmake")
    assert 'include("mytoolchain.cmake")' in toolchain


def test_cmake_toolchain_user_toolchain_from_dep():
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy
        class Pkg(ConanFile):
            exports_sources = "*"
            def package(self):
                copy(self, "*", self.build_folder, self.package_folder)
            def package_info(self):
                f = os.path.join(self.package_folder, "mytoolchain.cmake")
                self.conf_info.append("tools.cmake.cmaketoolchain:user_toolchain", f)
        """)
    client.save({"conanfile.py": conanfile,
                 "mytoolchain.cmake": 'message(STATUS "mytoolchain.cmake !!!running!!!")'})
    client.run("create . --name=toolchain --version=0.1")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "CMakeLists.txt"
            build_requires = "toolchain/0.1"
            generators = "CMakeToolchain"
            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)

    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": gen_cmakelists()}, clean_first=True)
    client.run("create . --name=pkg --version=0.1")
    assert "mytoolchain.cmake !!!running!!!" in client.out


def test_cmake_toolchain_without_build_type():
    # If "build_type" is not defined, toolchain will still be generated, it will not crash
    # Main effect is CMAKE_MSVC_RUNTIME_LIBRARY not being defined
    client = TestClient(path_with_spaces=False)
    conanfile = GenConanfile().with_settings("os", "compiler", "arch").\
        with_generator("CMakeToolchain")

    client.save({"conanfile.py": conanfile})
    client.run("install .")
    toolchain = client.load("conan_toolchain.cmake")
    assert "CMAKE_MSVC_RUNTIME_LIBRARY" not in toolchain
    assert "CMAKE_BUILD_TYPE" not in toolchain


@pytest.mark.skipif(platform.system() != "Windows", reason="Only on Windows with msvc")
@pytest.mark.tool("cmake")
def test_cmake_toolchain_cmake_vs_debugger_environment():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_package_type("shared-library")
                                                           .with_settings("build_type")})
    client.run("create . -s build_type=Release")
    client.run("create . -s build_type=Debug")
    client.run("create . -s build_type=MinSizeRel")

    client.run("install --require=pkg/1.0 -s build_type=Debug -g CMakeToolchain --format=json")
    debug_graph = json.loads(client.stdout)
    debug_bindir = debug_graph['graph']['nodes']['1']['cpp_info']['root']['bindirs'][0]
    debug_bindir = debug_bindir.replace('\\', '/')

    toolchain = client.load("conan_toolchain.cmake")
    debugger_environment = f"PATH=$<$<CONFIG:Debug>:{debug_bindir}>;%PATH%"
    assert debugger_environment in toolchain

    client.run("install --require=pkg/1.0 -s build_type=Release -g CMakeToolchain --format=json")
    release_graph = json.loads(client.stdout)
    release_bindir = release_graph['graph']['nodes']['1']['cpp_info']['root']['bindirs'][0]
    release_bindir = release_bindir.replace('\\', '/')

    toolchain = client.load("conan_toolchain.cmake")
    debugger_environment = f"PATH=$<$<CONFIG:Debug>:{debug_bindir}>" \
                           f"$<$<CONFIG:Release>:{release_bindir}>;%PATH%"
    assert debugger_environment in toolchain

    client.run("install --require=pkg/1.0 -s build_type=MinSizeRel -g CMakeToolchain --format=json")
    minsizerel_graph = json.loads(client.stdout)
    minsizerel_bindir = minsizerel_graph['graph']['nodes']['1']['cpp_info']['root']['bindirs'][0]
    minsizerel_bindir = minsizerel_bindir.replace('\\', '/')

    toolchain = client.load("conan_toolchain.cmake")
    debugger_environment = f"PATH=$<$<CONFIG:Debug>:{debug_bindir}>" \
                           f"$<$<CONFIG:Release>:{release_bindir}>" \
                           f"$<$<CONFIG:MinSizeRel>:{minsizerel_bindir}>;%PATH%"
    assert debugger_environment in toolchain


@pytest.mark.tool("cmake")
def test_cmake_toolchain_cmake_vs_debugger_environment_not_needed():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_package_type("shared-library")
                                                           .with_settings("build_type")})
    client.run("create . -s build_type=Release")

    cmake_generator = "" if platform.system() != "Windows" else "-c tools.cmake.cmaketoolchain:generator=Ninja"
    client.run(f"install --require=pkg/1.0 -s build_type=Release -g CMakeToolchain {cmake_generator}")
    toolchain = client.load("conan_toolchain.cmake")
    assert "CMAKE_VS_DEBUGGER_ENVIRONMENT" not in toolchain


@pytest.mark.tool("cmake")
def test_cmake_toolchain_multiple_user_toolchain():
    """ A consumer consuming two packages that declare:
            self.conf_info["tools.cmake.cmaketoolchain:user_toolchain"]
        The consumer wants to use apply both toolchains in the CMakeToolchain.
        There are two ways to customize the CMakeToolchain (parametrized):
                1. Altering the context of the block (with_context = True)
                2. Using the t.blocks["user_toolchain"].user_toolchains = [] (with_context = False)
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy
        class Pkg(ConanFile):
            exports_sources = "*"
            def package(self):
                copy(self, "*", self.source_folder, self.package_folder)
            def package_info(self):
                f = os.path.join(self.package_folder, "mytoolchain.cmake")
                self.conf_info.append("tools.cmake.cmaketoolchain:user_toolchain", f)
        """)
    client.save({"conanfile.py": conanfile,
                 "mytoolchain.cmake": 'message(STATUS "mytoolchain1.cmake !!!running!!!")'})
    client.run("create . --name=toolchain1 --version=0.1")
    client.save({"conanfile.py": conanfile,
                 "mytoolchain.cmake": 'message(STATUS "mytoolchain2.cmake !!!running!!!")'})
    client.run("create . --name=toolchain2 --version=0.1")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "CMakeLists.txt"
            tool_requires = "toolchain1/0.1", "toolchain2/0.1"
            generators = "CMakeToolchain"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)

    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": gen_cmakelists()}, clean_first=True)
    client.run("create . --name=pkg --version=0.1")
    assert "mytoolchain1.cmake !!!running!!!" in client.out
    assert "mytoolchain2.cmake !!!running!!!" in client.out
    assert "CMake Warning" not in client.out


@pytest.mark.tool("cmake")
def test_cmaketoolchain_no_warnings():
    """Make sure uninitialized variables do not cause any warnings, passing -Werror=dev
    and --warn-uninitialized, calling "cmake" with conan_toolchain.cmake used to fail
    """
    # Issue https://github.com/conan-io/conan/issues/10288
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Conan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            generators = "CMakeToolchain", "CMakeDeps"
            requires = "dep/0.1"
        """)
    consumer = textwrap.dedent("""
       cmake_minimum_required(VERSION 3.15)
       project(MyHello NONE)

       find_package(dep CONFIG REQUIRED)
       """)
    client.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
                 "conanfile.py": conanfile,
                 "CMakeLists.txt": consumer})

    client.run("create dep")
    client.run("install .")
    build_type = "-DCMAKE_BUILD_TYPE=Release" if platform.system() != "Windows" else ""
    client.run_command("cmake -Werror=dev --warn-uninitialized . {}"
                       " -DCMAKE_TOOLCHAIN_FILE=./conan_toolchain.cmake".format(build_type))
    assert "Using Conan toolchain" in client.out
    # The real test is that there are no errors, it returns successfully


def test_install_output_directories():
    """
    If we change the libdirs of the cpp.package, as we are doing cmake.install, the output directory
    for the libraries is changed
    """
    client = TestClient()
    client.run("new cmake_lib -d name=zlib -d version=1.2.11")
    # Edit the cpp.package.libdirs and check if the library is placed anywhere else
    cf = client.load("conanfile.py")
    cf = cf.replace("cmake_layout(self)",
                    'cmake_layout(self)\n        self.cpp.package.libdirs = ["mylibs"]')
    client.save({"conanfile.py": cf})
    client.run("create . -tf=")
    layout = client.created_layout()
    p_folder = layout.package()
    assert os.path.exists(os.path.join(p_folder, "mylibs"))
    assert not os.path.exists(os.path.join(p_folder, "lib"))

    b_folder = layout.build()
    if platform.system() != "Windows":
        gen_folder = os.path.join(b_folder, "build", "Release", "generators")
    else:
        gen_folder = os.path.join(b_folder, "build", "generators")

    toolchain = client.load(os.path.join(gen_folder, "conan_toolchain.cmake"))
    assert 'set(CMAKE_INSTALL_LIBDIR "mylibs")' in toolchain


@pytest.mark.tool("cmake")
def test_cmake_toolchain_definitions_complex_strings():
    # https://github.com/conan-io/conan/issues/11043
    client = TestClient(path_with_spaces=False)
    profile = textwrap.dedent(r'''
        include(default)
        [conf]
        tools.build:defines+=["escape=partially \"escaped\""]
        tools.build:defines+=["spaces=me you"]
        tools.build:defines+=["foobar=bazbuz"]
        tools.build:defines+=["answer=42"]
    ''')

    conanfile = textwrap.dedent(r'''
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout

        class Test(ConanFile):
            exports_sources = "CMakeLists.txt", "src/*"
            settings = "os", "compiler", "arch", "build_type"

            def generate(self):
                tc = CMakeToolchain(self)
                tc.preprocessor_definitions["escape2"] = "partially \"escaped\""
                tc.preprocessor_definitions["spaces2"] = "me you"
                tc.preprocessor_definitions["foobar2"] = "bazbuz"
                tc.preprocessor_definitions["answer2"] = 42
                tc.preprocessor_definitions["NOVALUE_DEF"] = None
                tc.preprocessor_definitions.release["escape_release"] = "release partially \"escaped\""
                tc.preprocessor_definitions.release["spaces_release"] = "release me you"
                tc.preprocessor_definitions.release["foobar_release"] = "release bazbuz"
                tc.preprocessor_definitions.release["answer_release"] = 42
                tc.preprocessor_definitions.release["NOVALUE_DEF_RELEASE"] = None

                tc.preprocessor_definitions.debug["escape_debug"] = "debug partially \"escaped\""
                tc.preprocessor_definitions.debug["spaces_debug"] = "debug me you"
                tc.preprocessor_definitions.debug["foobar_debug"] = "debug bazbuz"
                tc.preprocessor_definitions.debug["answer_debug"] = 21
                tc.generate()

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        ''')

    main = textwrap.dedent("""
        #include <stdio.h>
        #define STR(x)   #x
        #define SHOW_DEFINE(x) printf("%s=%s", #x, STR(x))
        int main(int argc, char *argv[]) {
            SHOW_DEFINE(escape);
            SHOW_DEFINE(spaces);
            SHOW_DEFINE(foobar);
            SHOW_DEFINE(answer);
            SHOW_DEFINE(escape2);
            SHOW_DEFINE(spaces2);
            SHOW_DEFINE(foobar2);
            SHOW_DEFINE(answer2);
            #ifdef NDEBUG
            SHOW_DEFINE(escape_release);
            SHOW_DEFINE(spaces_release);
            SHOW_DEFINE(foobar_release);
            SHOW_DEFINE(answer_release);
            #else
            SHOW_DEFINE(escape_debug);
            SHOW_DEFINE(spaces_debug);
            SHOW_DEFINE(foobar_debug);
            SHOW_DEFINE(answer_debug);
            #endif
            #ifdef NOVALUE_DEF
            printf("NO VALUE!!!!");
            #endif
            #ifdef NOVALUE_DEF_RELEASE
            printf("NO VALUE RELEASE!!!!");
            #endif
            return 0;
        }
        """)

    cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(Test CXX)
        set(CMAKE_CXX_STANDARD 11)
        add_executable(example src/main.cpp)
        """)

    client.save({"conanfile.py": conanfile, "profile": profile, "src/main.cpp": main,
                 "CMakeLists.txt": cmakelists}, clean_first=True)
    client.run("install . -pr=./profile")
    client.run("build . -pr=./profile")
    exe = "build/Release/example" if platform.system() != "Windows" else r"build\Release\example.exe"
    client.run_command(exe)
    assert 'escape=partially "escaped"' in client.out
    assert 'spaces=me you' in client.out
    assert 'foobar=bazbuz' in client.out
    assert 'answer=42' in client.out
    assert 'escape2=partially "escaped"' in client.out
    assert 'spaces2=me you' in client.out
    assert 'foobar2=bazbuz' in client.out
    assert 'answer2=42' in client.out
    assert 'escape_release=release partially "escaped"' in client.out
    assert 'spaces_release=release me you' in client.out
    assert 'foobar_release=release bazbuz' in client.out
    assert 'answer_release=42' in client.out
    assert "NO VALUE!!!!" in client.out
    assert "NO VALUE RELEASE!!!!" in client.out

    client.run("install . -pr=./profile -s build_type=Debug")
    client.run("build . -pr=./profile -s build_type=Debug")
    exe = "build/Debug/example" if platform.system() != "Windows" else r"build\Debug\example.exe"

    client.run_command(exe)
    assert 'escape_debug=debug partially "escaped"' in client.out
    assert 'spaces_debug=debug me you' in client.out
    assert 'foobar_debug=debug bazbuz' in client.out
    assert 'answer_debug=21' in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
def test_cmake_toolchain_runtime_types():
    # everything works with the default cmake_minimum_required version 3.15 in the template
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_lib -d name=hello -d version=0.1")
    client.run("install . -s compiler.runtime=static -s build_type=Debug")
    client.run("build . -s compiler.runtime=static -s build_type=Debug")

    vcvars = vcvars_command(version="15", architecture="x64")
    lib = os.path.join(client.current_folder, "build", "Debug", "hello.lib")
    dumpbind_cmd = '{} && dumpbin /directives "{}"'.format(vcvars, lib)
    client.run_command(dumpbind_cmd)
    assert "LIBCMTD" in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
def test_cmake_toolchain_runtime_types_cmake_older_than_3_15():
    client = TestClient(path_with_spaces=False)
    # Setting an older cmake_minimum_required in the CMakeLists fails, will link
    # against the default debug runtime (MDd->MSVCRTD), not against MTd->LIBCMTD
    client.run("new cmake_lib -d name=hello -d version=0.1")
    cmake = client.load("CMakeLists.txt")
    cmake2 = cmake.replace('cmake_minimum_required(VERSION 3.15)',
                           'cmake_minimum_required(VERSION 3.1)')
    assert cmake != cmake2
    client.save({"CMakeLists.txt": cmake2})

    client.run("install . -s compiler.runtime=static -s build_type=Debug")
    client.run("build . -s compiler.runtime=static -s build_type=Debug")

    vcvars = vcvars_command(version="15", architecture="x64")
    lib = os.path.join(client.current_folder, "build", "Debug", "hello.lib")
    dumpbind_cmd = '{} && dumpbin /directives "{}"'.format(vcvars, lib)
    client.run_command(dumpbind_cmd)
    assert "LIBCMTD" in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
class TestWinSDKVersion:

    @pytest.mark.tool("cmake", "3.23")
    @pytest.mark.tool("visual_studio", "17")
    def test_cmake_toolchain_winsdk_version(self):
        # This test passes also with CMake 3.28, as long as cmake_minimum_required(VERSION 3.27)
        # is not defined
        client = TestClient(path_with_spaces=False)
        client.run("new cmake_lib -d name=hello -d version=0.1")
        cmake = client.load("CMakeLists.txt")
        cmake += 'message(STATUS "CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION = ' \
                 '${CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION}")'
        client.save({"CMakeLists.txt": cmake})
        client.run("create . -s arch=x86_64 -s compiler.version=194 "
                   "-c tools.microsoft:winsdk_version=10.0")
        assert "CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION = 10.0" in client.out
        assert "Conan toolchain: CMAKE_GENERATOR_PLATFORM=x64" in client.out
        assert "Conan toolchain: CMAKE_GENERATOR_PLATFORM=x64,version" not in client.out

    @pytest.mark.tool("cmake", "3.27")
    @pytest.mark.tool("visual_studio", "17")
    def test_cmake_toolchain_winsdk_version2(self):
        # https://github.com/conan-io/conan/issues/15372
        client = TestClient(path_with_spaces=False)
        client.run("new cmake_lib -d name=hello -d version=0.1")
        cmake = client.load("CMakeLists.txt")
        cmake = cmake.replace("cmake_minimum_required(VERSION 3.15)",
                              "cmake_minimum_required(VERSION 3.27)")
        cmake += 'message(STATUS "CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION = ' \
                 '${CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION}")'
        client.save({"CMakeLists.txt": cmake})
        client.run("create . -s arch=x86_64 -s compiler.version=194 "
                   "-c tools.microsoft:winsdk_version=10.0 "
                   '-c tools.cmake.cmaketoolchain:generator="Visual Studio 17"')
        assert "CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION = 10.0" in client.out
        assert "Conan toolchain: CMAKE_GENERATOR_PLATFORM=x64,version=10.0" in client.out


@pytest.mark.tool("cmake", "3.23")
def test_cmake_layout_missing_option():
    client = TestClient(path_with_spaces=False)

    client.run("new cmake_exe -d name=hello -d version=0.1")
    settings_layout = '-c tools.cmake.cmake_layout:build_folder_vars=\'["options.missing"]\' ' \
                      '-c tools.cmake.cmaketoolchain:generator=Ninja'
    client.run("install . {}".format(settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, "build", "Release", "generators"))


@pytest.mark.tool("cmake", "3.23")
def test_cmake_layout_missing_setting():
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_exe -d name=hello -d version=0.1")
    settings_layout = '-c tools.cmake.cmake_layout:build_folder_vars=\'["settings.missing"]\' ' \
                      '-c tools.cmake.cmaketoolchain:generator=Ninja'
    client.run("install . {}".format(settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, "build", "Release", "generators"))


@pytest.mark.tool("cmake")
def test_cmaketoolchain_sysroot():
    client = TestClient(path_with_spaces=False)

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout

        class AppConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "CMakeLists.txt"

            def generate(self):
                tc = CMakeToolchain(self)
                {}
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        """)

    cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(app NONE)
        message("sysroot: '${CMAKE_SYSROOT}'")
        message("osx_sysroot: '${CMAKE_OSX_SYSROOT}'")
        """)

    client.save({
        "conanfile.py": conanfile.format(""),
        "CMakeLists.txt": cmakelist
    })

    fake_sysroot = client.current_folder
    output_fake_sysroot = fake_sysroot.replace("\\", "/") if platform.system() == "Windows" else fake_sysroot
    client.run("create . --name=app --version=1.0 -c tools.build:sysroot='{}'".format(fake_sysroot))
    assert "sysroot: '{}'".format(output_fake_sysroot) in client.out

    # set in a block instead of using conf
    set_sysroot_in_block = 'tc.blocks["generic_system"].values["cmake_sysroot"] = "{}"'.format(output_fake_sysroot)
    client.save({
        "conanfile.py": conanfile.format(set_sysroot_in_block),
    })
    client.run("create . --name=app --version=1.0")
    assert "sysroot: '{}'".format(output_fake_sysroot) in client.out


def test_cmake_layout_not_forbidden_build_type():
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_exe -d name=hello -d version=0.1")
    settings_layout = '-c tools.cmake.cmake_layout:build_folder_vars=' \
                      '\'["options.missing", "settings.build_type"]\''
    client.run("install . {}".format(settings_layout))
    assert os.path.exists(os.path.join(client.current_folder,
                                       "build/release/generators/conan_toolchain.cmake"))


def test_resdirs_cmake_install():
    """If resdirs is declared, the CMAKE_INSTALL_DATAROOTDIR folder is set"""

    client = TestClient(path_with_spaces=False)

    conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout

            class AppConan(ConanFile):
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = "CMakeLists.txt", "my_license"
                name = "foo"
                version = "1.0"

                def generate(self):
                    tc = CMakeToolchain(self)
                    tc.generate()

                def layout(self):
                    self.cpp.package.resdirs = ["res"]

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()

                def package(self):
                    cmake = CMake(self)
                    cmake.install()
            """)

    cmake = """
    cmake_minimum_required(VERSION 3.15)
    project(foo NONE)
    if(NOT CMAKE_INSTALL_DATAROOTDIR)
        message(FATAL_ERROR "Cannot install stuff")
    endif()
    install(FILES my_license DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/licenses)
    """

    client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmake, "my_license": "MIT"})
    client.run("create .")
    assert "/res/licenses/my_license" in client.out
    assert "Packaged 1 file: my_license" in client.out


def test_resdirs_none_cmake_install():
    """If no resdirs are declared, the CMAKE_INSTALL_DATAROOTDIR folder is not set"""

    client = TestClient(path_with_spaces=False)

    conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout

            class AppConan(ConanFile):
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = "CMakeLists.txt", "my_license"
                name = "foo"
                version = "1.0"

                def generate(self):
                    tc = CMakeToolchain(self)
                    tc.generate()

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()

                def package(self):
                    cmake = CMake(self)
                    cmake.install()
            """)

    cmake = """
    cmake_minimum_required(VERSION 3.15)
    project(foo NONE)
    if(NOT CMAKE_INSTALL_DATAROOTDIR)
        message(FATAL_ERROR "Cannot install stuff")
    endif()
    """

    client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmake, "my_license": "MIT"})
    client.run("create .", assert_error=True)
    assert "Cannot install stuff" in client.out


@pytest.mark.tool("cmake")
def test_cmake_toolchain_vars_when_option_declared():
    t = TestClient()

    cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 2.8) # <---- set this to an old version for old policies
    cmake_policy(SET CMP0091 NEW) # <-- Needed on Windows
    project(mylib CXX)

    message("CMake version: ${CMAKE_VERSION}")

    # Set the options AFTER the call to project, that is, after toolchain is loaded
    option(BUILD_SHARED_LIBS "" ON)
    option(CMAKE_POSITION_INDEPENDENT_CODE "" OFF)

    add_library(mylib src/mylib.cpp)
    target_include_directories(mylib PUBLIC include)

    get_target_property(MYLIB_TARGET_TYPE mylib TYPE)
    get_target_property(MYLIB_PIC mylib POSITION_INDEPENDENT_CODE)
    message("mylib target type: ${MYLIB_TARGET_TYPE}")
    message("MYLIB_PIC value: ${MYLIB_PIC}")
    if(MYLIB_PIC)
        #Note: the value is "True"/"False" if set by cmake,
        #       and "ON"/"OFF" if set by Conan
        message("mylib position independent code: ON")
    else()
        message("mylib position independent code: OFF")
    endif()

    set_target_properties(mylib PROPERTIES PUBLIC_HEADER "include/mylib.h")
    install(TARGETS mylib)
    """)

    t.run("new cmake_lib -d name=mylib -d version=1.0")
    t.save({"CMakeLists.txt": cmakelists})

    # The generated toolchain should set `BUILD_SHARED_LIBS` to `OFF`,
    # and `CMAKE_POSITION_INDEPENDENT_CODE` to `ON` and the calls to
    # `option()` in the CMakeLists.txt should respect the existing values.
    # Note: on *WINDOWS* `fPIC` is not an option for this recipe, so it's invalid
    #       to pass it to Conan, in which case the value in CMakeLists.txt
    #       takes precedence.
    fpic_option = "-o mylib/*:fPIC=True" if platform.system() != "Windows" else ""
    fpic_cmake_value = "ON" if platform.system() != "Windows" else "OFF"
    t.run(f"create . -o mylib/*:shared=False {fpic_option} --test-folder=")
    assert "mylib target type: STATIC_LIBRARY" in t.out
    assert f"mylib position independent code: {fpic_cmake_value}" in t.out

    # When building manually, ensure the value passed by the toolchain overrides the ones in
    # the CMakeLists
    fpic_option = "-o mylib/*:fPIC=False" if platform.system() != "Windows" else ""
    t.run(f"install . -o mylib/*:shared=False {fpic_option}")
    folder = "build/generators" if platform.system() == "Windows" else "build/Release/generators"
    t.run_command(f"cmake -S . -B build/ -DCMAKE_TOOLCHAIN_FILE={folder}/conan_toolchain.cmake")
    assert "mylib target type: STATIC_LIBRARY" in t.out
    assert f"mylib position independent code: OFF" in t.out

    # Note: from this point forward, the CMakeCache is already initialised.
    # When explicitly overriding `CMAKE_POSITION_INDEPENDENT_CODE` via command line, ensure
    # this takes precedence to the value defined by the toolchain
    t.run_command("cmake -S . -B build/ -DCMAKE_POSITION_INDEPENDENT_CODE=ON")
    assert "mylib target type: STATIC_LIBRARY" in t.out
    assert "mylib position independent code: ON" in t.out

    t.run_command("cmake -S . -B build/ -DBUILD_SHARED_LIBS=ON")
    assert "mylib target type: SHARED_LIBRARY" in t.out
    assert "mylib position independent code: ON" in t.out


@pytest.mark.tool("cmake")
@pytest.mark.parametrize("single_profile", [True, False])
def test_find_program_for_tool_requires(single_profile):
    """Test that the same reference can be both a tool_requires and a regular requires,
    and that find_program (executables) and find_package (libraries) find the correct ones
    when cross building.
    """

    client = TestClient()

    conanfile = textwrap.dedent("""
        import os

        from conan import ConanFile
        from conan.tools.files import copy
        class TestConan(ConanFile):
            name = "foobar"
            version = "1.0"
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = "*"
            def layout(self):
                pass
            def package(self):
                copy(self, pattern="lib*", src=self.build_folder, dst=os.path.join(self.package_folder, "lib"))
                copy(self, pattern="*bin", src=self.build_folder, dst=os.path.join(self.package_folder, "bin"))
    """)

    host_profile = textwrap.dedent("""
    [settings]
        os=Linux
        arch=armv8
        compiler=gcc
        compiler.version=12
        compiler.libcxx=libstdc++11
        build_type=Release
    """)

    build_profile = textwrap.dedent("""
        [settings]
        os=Linux
        arch=x86_64
        compiler=gcc
        compiler.version=12
        compiler.libcxx=libstdc++11
        build_type=Release
    """)

    client.save({"conanfile.py": conanfile,
                "libfoo.so": "",
                "foobin": "",
                "host_profile": host_profile,
                "build_profile": build_profile
                })

    client.run("create . -pr:b build_profile -pr:h build_profile")
    build_context_package_folder = re.search(r"Package folder ([\w\W]+).conan2([\w\W]+)", str(client.out)).group(2).strip()
    build_context_package_folder = build_context_package_folder.replace("\\", "/")
    client.run("create . -pr:b build_profile -pr:h host_profile")
    host_context_package_folder = re.search(r"Package folder ([\w\W]+).conan2([\w\W]+)", str(client.out)).group(2).strip()
    host_context_package_folder = host_context_package_folder.replace("\\", "/")

    conanfile_consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout
        class PkgConan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"

            def layout(self):
                cmake_layout(self)

            def requirements(self):
                self.requires("foobar/1.0")

            def build_requirements(self):
               self.tool_requires("foobar/1.0")
    """)

    cmakelists_consumer = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(Hello LANGUAGES NONE)
        find_package(foobar CONFIG REQUIRED)
        find_program(FOOBIN_EXECUTABLE foobin)
        message("foobin executable: ${FOOBIN_EXECUTABLE}")
        message("foobar include dir: ${foobar_INCLUDE_DIR}")
        if(NOT FOOBIN_EXECUTABLE)
          message(FATAL_ERROR "FOOBIN executable not found")
        endif()
    """)

    client.save({
        "conanfile_consumer.py": conanfile_consumer,
        "CMakeLists.txt": cmakelists_consumer,
        "host_profile": host_profile,
        "build_profile": build_profile}, clean_first=True)

    client.run("install conanfile_consumer.py -g CMakeToolchain -g CMakeDeps -pr:b build_profile -pr:h host_profile")

    with client.chdir("build"):
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=Release/generators/conan_toolchain.cmake -DCMAKE_BUILD_TYPE=Release")
        # Verify binary executable is found from build context package,
        # and library comes from host context package
        assert f"{build_context_package_folder}/bin/foobin" in client.out
        assert f"{host_context_package_folder}/include" in client.out


@pytest.mark.tool("pkg_config")
def test_cmaketoolchain_and_pkg_config_path():
    """
    Lightweight test which is loading a dependency as a *.pc file through
    CMake thanks to pkg_check_modules macro.
    It's working because PKG_CONFIG_PATH env variable is being loaded automatically
    by the CMakeToolchain generator.
    """
    client = TestClient()
    dep = textwrap.dedent("""
    from conan import ConanFile
    class DepConan(ConanFile):
        name = "dep"
        version = "1.0"
        def package_info(self):
            self.cpp_info.libs = ["dep"]
    """)
    pkg = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.cmake import CMake, cmake_layout
    class HelloConan(ConanFile):
        name = "pkg"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"
        generators = "PkgConfigDeps", "CMakeToolchain"
        exports_sources = "CMakeLists.txt"

        def requirements(self):
            self.requires("dep/1.0")

        def layout(self):
            cmake_layout(self)

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()
    """)
    cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(pkg NONE)

    find_package(PkgConfig REQUIRED)
    # We should have PKG_CONFIG_PATH created in the current environment
    pkg_check_modules(DEP REQUIRED IMPORTED_TARGET dep)
    """)
    client.save({
        "dep/conanfile.py": dep,
        "pkg/conanfile.py": pkg,
        "pkg/CMakeLists.txt": cmakelists
    })
    client.run("create dep/conanfile.py")
    client.run("create pkg/conanfile.py")
    assert "Found dep, version 1.0" in client.out


def test_cmaketoolchain_conf_from_tool_require():
    # https://github.com/conan-io/conan/issues/13914
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Conan(ConanFile):
            name = "toolchain"
            version = "1.0"

            def package_info(self):
                self.conf_info.define("tools.cmake.cmaketoolchain:system_name", "GENERIC-POTATO")
                self.conf_info.define("tools.cmake.cmaketoolchain:system_processor", "ARM-POTATO")
                self.conf_info.define("tools.build.cross_building:can_run", False)
                self.conf_info.define("tools.build:compiler_executables", {
                    "c": "arm-none-eabi-gcc",
                    "cpp": "arm-none-eabi-g++",
                    "asm": "arm-none-eabi-as",
                })
        """)
    c.save({"conanfile.py": conanfile,
            "test_package/conanfile.py": GenConanfile().with_test("pass")
                                                       .with_tool_requires("toolchain/1.0")
                                                       .with_generator("CMakeToolchain")})
    c.run("create .")
    toolchain = c.load("test_package/conan_toolchain.cmake")
    assert "set(CMAKE_SYSTEM_NAME GENERIC-POTATO)" in toolchain
    assert "set(CMAKE_SYSTEM_PROCESSOR ARM-POTATO)" in toolchain


def test_inject_user_toolchain():
    client = TestClient()

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class AppConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "CMakeLists.txt"
            name = "foo"
            version = "1.0"
            generators = "CMakeToolchain"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        """)

    cmake = """
        cmake_minimum_required(VERSION 3.15)
        project(foo LANGUAGES NONE)
        message(STATUS "MYVAR1 ${MY_USER_VAR1}!!")
    """
    profile = textwrap.dedent("""
        include(default)
        [conf]
        tools.cmake.cmaketoolchain:user_toolchain+={{profile_dir}}/myvars.cmake""")
    save(os.path.join(client.paths.profiles_path, "myprofile"), profile)
    save(os.path.join(client.paths.profiles_path, "myvars.cmake"), 'set(MY_USER_VAR1 "MYVALUE1")')
    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": cmake})
    client.run("build . -pr=myprofile")
    assert "-- MYVAR1 MYVALUE1!!" in client.out

    # Now test with the global.conf
    global_conf = 'tools.cmake.cmaketoolchain:user_toolchain=' \
                  '["{{conan_home_folder}}/my.cmake"]'
    client.save_home({"global.conf": global_conf})
    save(os.path.join(client.cache_folder, "my.cmake"), 'message(STATUS "IT WORKS!!!!")')
    client.run("build .")
    # The toolchain is found and can be used
    assert "IT WORKS!!!!" in client.out


def test_no_build_type():
    client = TestClient()

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain

        class AppConan(ConanFile):
            name = "pkg"
            version = "1.0"
            settings = "os", "compiler", "arch"
            exports_sources = "CMakeLists.txt"

            def layout(self):
                self.folders.build = "build"

            def generate(self):
                tc = CMakeToolchain(self)
                if not tc.is_multi_configuration:
                    tc.cache_variables["CMAKE_BUILD_TYPE"] = "Release"
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                build_type = "Release" if cmake.is_multi_configuration else None
                cmake.build(build_type=build_type)

            def package(self):
                cmake = CMake(self)
                build_type = "Release" if cmake.is_multi_configuration else None
                cmake.install(build_type=build_type)
        """)

    cmake = """
        cmake_minimum_required(VERSION 3.15)
        project(pkg LANGUAGES NONE)
    """

    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": cmake})
    client.run("create .")
    assert "Don't specify 'build_type' at build time" not in client.out


@pytest.mark.tool("cmake", "3.19")
def test_redirect_stdout():
    client = TestClient()
    conanfile = textwrap.dedent("""
    import os
    from io import StringIO
    from conan import ConanFile
    from conan.tools.cmake import CMake, CMakeToolchain
    from conan.tools.cmake import cmake_layout

    class Pkg(ConanFile):
        name = "foo"
        version = "1.0"
        settings = "os", "arch", "build_type", "compiler"
        generators = "CMakeToolchain"
        exports_sources = "CMakeLists.txt", "main.cpp"

        def build(self):
            cmake = CMake(self)

            config_stdout, config_stderr = StringIO(), StringIO()
            cmake.configure(stdout=config_stdout, stderr=config_stderr)
            self.output.info(f"Configure stdout: '{config_stdout.getvalue()}'")
            self.output.info(f"Configure stderr: '{config_stderr.getvalue()}'")

            build_stdout, build_stderr = StringIO(), StringIO()
            cmake.build(stdout=build_stdout, stderr=build_stderr)
            self.output.info(f"Build stdout: '{build_stdout.getvalue()}'")
            self.output.info(f"Build stderr: '{build_stderr.getvalue()}'")

            test_stdout, test_stderr = StringIO(), StringIO()
            cmake.test(stdout=test_stdout, stderr=test_stderr)
            self.output.info(f"Test stdout: '{test_stdout.getvalue()}'")
            self.output.info(f"Test stderr: '{test_stderr.getvalue()}'")

        def package(self):
            cmake = CMake(self)
            install_stdout, install_stderr = StringIO(), StringIO()
            cmake.install(stdout=install_stdout, stderr=install_stderr)
            self.output.info(f"Install stdout: '{install_stdout.getvalue()}'")
            self.output.info(f"Install stderr: '{install_stderr.getvalue()}'")


    """)
    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": 'project(foo)\nadd_executable(mylib main.cpp)\ninclude(CTest)',
                 "main.cpp": "int main() {return 0;}"})
    client.run("create .")

    # Ensure the output is not unexpectedly empty
    assert re.search("Configure stdout: '[^']", client.out)
    assert re.search("Configure stderr: '[^']", client.out)

    assert re.search("Build stdout: '[^']", client.out)
    assert re.search("Build stderr: ''", client.out)

    assert re.search("Test stdout: '[^']", client.out)

    # Empty on Windows
    if platform.system() == "Windows":
        assert re.search("Test stderr: ''", client.out)
    else:
        assert re.search("Test stderr: '[^']", client.out)

    if platform.system() == "Windows":
        assert re.search("Install stdout: ''", client.out)
    else:
        assert re.search("Install stdout: '[^']", client.out)
    assert re.search("Install stderr: ''", client.out)


@pytest.mark.tool("cmake")
@pytest.mark.skipif(platform.system() != "Windows", reason="neeed multi-config")
def test_cmake_toolchain_cxxflags_multi_config():
    c = TestClient()
    profile_release = textwrap.dedent(r"""
        include(default)
        [conf]
        tools.build:defines=["conan_test_answer=42", "conan_test_other=24"]
        tools.build:cxxflags=["/Zc:__cplusplus"]
        """)
    profile_debug = textwrap.dedent(r"""
        include(default)
        [settings]
        build_type=Debug
        [conf]
        tools.build:defines=["conan_test_answer=123"]
        tools.build:cxxflags=["/W4"]
        """)

    conanfile = textwrap.dedent(r'''
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout

        class Test(ConanFile):
            exports_sources = "CMakeLists.txt", "src/*"
            settings = "os", "compiler", "arch", "build_type"
            generators = "CMakeToolchain"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        ''')

    main = textwrap.dedent(r"""
        #include <iostream>
        #include <stdio.h>

        #define STR(x)   #x
        #define SHOW_DEFINE(x) printf("DEFINE %s=%s!\n", #x, STR(x))

        int main() {
            SHOW_DEFINE(conan_test_answer);
            #ifdef conan_test_other
            SHOW_DEFINE(conan_test_other);
            #endif
            char a = 123L;  // to trigger warnings

            #if __cplusplus
            std::cout << "CPLUSPLUS: __cplusplus" << __cplusplus<< "\n";
            #endif
        }
        """)

    cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(Test CXX)
        add_executable(example src/main.cpp)
        """)

    c.save({"conanfile.py": conanfile,
            "profile_release": profile_release,
            "profile_debug": profile_debug,
            "src/main.cpp": main,
            "CMakeLists.txt": cmakelists}, clean_first=True)
    c.run("install . -pr=./profile_release")
    c.run("install . -pr=./profile_debug")

    with c.chdir("build"):
        c.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=generators/conan_toolchain.cmake")
        c.run_command("cmake --build . --config Release")
        assert "warning C4189" not in c.out
        c.run_command("cmake --build . --config Debug")
        assert "warning C4189" in c.out

    c.run_command(r"build\Release\example.exe")
    assert 'DEFINE conan_test_answer=42!' in c.out
    assert 'DEFINE conan_test_other=24!' in c.out
    assert "CPLUSPLUS: __cplusplus20" in c.out

    c.run_command(r"build\Debug\example.exe")
    assert 'DEFINE conan_test_answer=123' in c.out
    assert 'other=' not in c.out
    assert "CPLUSPLUS: __cplusplus19" in c.out


@pytest.mark.tool("ninja")
@pytest.mark.tool("cmake", "3.23")
def test_cmake_toolchain_ninja_multi_config():
    c = TestClient()
    profile_release = textwrap.dedent(r"""
        include(default)
        [conf]
        tools.cmake.cmaketoolchain:generator=Ninja Multi-Config
        tools.build:defines=["conan_test_answer=42", "conan_test_other=24"]
        """)
    profile_debug = textwrap.dedent(r"""
        include(default)
        [settings]
        build_type=Debug
        [conf]
        tools.cmake.cmaketoolchain:generator=Ninja Multi-Config
        tools.build:defines=["conan_test_answer=123"]
        """)
    profile_relwithdebinfo = textwrap.dedent(r"""
        include(default)
        [settings]
        build_type=RelWithDebInfo
        [conf]
        tools.cmake.cmaketoolchain:generator=Ninja Multi-Config
        tools.build:defines=["conan_test_answer=456", "conan_test_other=abc", 'conan_test_complex="1 2"']
        """)

    conanfile = textwrap.dedent(r'''
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout

        class Test(ConanFile):
            exports_sources = "CMakeLists.txt", "src/*"
            settings = "os", "compiler", "arch", "build_type"
            generators = "CMakeToolchain"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        ''')

    main = textwrap.dedent(r"""
        #include <iostream>
        #include <stdio.h>

        #define STR(x)   #x
        #define SHOW_DEFINE(x) printf("DEFINE %s=%s!\n", #x, STR(x))

        int main() {
            SHOW_DEFINE(conan_test_answer);
            #ifdef conan_test_other
            SHOW_DEFINE(conan_test_other);
            #endif
            #ifdef conan_test_complex
            SHOW_DEFINE(conan_test_complex);
            #endif
        }
        """)

    cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(Test CXX)
        add_executable(example src/main.cpp)
        """)

    c.save({"conanfile.py": conanfile,
            "profile_release": profile_release,
            "profile_debug": profile_debug,
            "profile_relwithdebinfo": profile_relwithdebinfo,
            "src/main.cpp": main,
            "CMakeLists.txt": cmakelists})
    c.run("install . -pr=./profile_release")
    c.run("install . -pr=./profile_debug")
    c.run("install . -pr=./profile_relwithdebinfo")

    with c.chdir("build"):
        env = r".\generators\conanbuild.bat &&" if platform.system() == "Windows" else ""
        c.run_command(f"{env} cmake .. -G \"Ninja Multi-Config\" "
                      "-DCMAKE_TOOLCHAIN_FILE=generators/conan_toolchain.cmake")
        c.run_command(f"{env} cmake --build . --config Release")
        c.run_command(f"{env} cmake --build . --config Debug")
        c.run_command(f"{env} cmake --build . --config RelWithDebInfo")

    c.run_command(os.sep.join([".", "build", "Release", "example"]))
    assert 'DEFINE conan_test_answer=42!' in c.out
    assert 'DEFINE conan_test_other=24!' in c.out
    assert 'complex=' not in c.out

    c.run_command(os.sep.join([".", "build", "Debug", "example"]))
    assert 'DEFINE conan_test_answer=123' in c.out
    assert 'other=' not in c.out
    assert 'complex=' not in c.out

    c.run_command(os.sep.join([".", "build", "RelWithDebInfo", "example"]))
    assert 'DEFINE conan_test_answer=456!' in c.out
    assert 'DEFINE conan_test_other=abc!' in c.out
    assert 'DEFINE conan_test_complex="1 2"!' in c.out


@pytest.mark.tool("cmake")
@pytest.mark.skipif(platform.system() != "Darwin", reason="Only needs to run once, no need for extra platforms")
def test_cxx_version_not_overriden_if_hardcoded():
    """Any C++ standard set in the CMakeLists.txt will have priority even if the
    compiler.cppstd is set in the profile"""
    tc = TestClient()
    tc.run("new cmake_exe -dname=foo -dversion=1.0")

    cml_contents = tc.load("CMakeLists.txt")
    cml_contents = cml_contents.replace("project(foo CXX)\n", "project(foo CXX)\nset(CMAKE_CXX_STANDARD 17)\n")
    tc.save({"CMakeLists.txt": cml_contents})

    # The compiler.cppstd will not override the CXX_STANDARD variable
    tc.run("create . -s=compiler.cppstd=11")
    assert "Conan toolchain: C++ Standard 11 with extensions OFF" in tc.out
    assert "Warning: Standard CMAKE_CXX_STANDARD value defined in conan_toolchain.cmake to 11 has been modified to 17" in tc.out

    # Even though Conan warns, the compiled code is C++17
    assert "foo/1.0: __cplusplus2017" in tc.out

    tc.run("create . -s=compiler.cppstd=17")
    assert "Conan toolchain: C++ Standard 17 with extensions OFF" in tc.out
    assert "Warning: Standard CMAKE_CXX_STANDARD value defined in conan_toolchain.cmake to 17 has been modified to 17" not in tc.out


@pytest.mark.tool("cmake", "3.23")  # Android complains if <3.19
@pytest.mark.tool("android_ndk")
@pytest.mark.skipif(platform.system() != "Darwin", reason="NDK only installed on MAC")
def test_cmake_toolchain_crossbuild_set_cmake_compiler():
    # To reproduce https://github.com/conan-io/conan/issues/16960
    # the issue happens when you set CMAKE_CXX_COMPILER and CMAKE_C_COMPILER as cache variables
    # and then cross-build
    c = TestClient()

    ndk_path = tools_locations["android_ndk"]["system"]["path"][platform.system()]
    bin_path = ndk_path + (
        "/toolchains/llvm/prebuilt/darwin-x86_64/bin" if platform.machine() == "x86_64" else
        "/toolchains/llvm/prebuilt/darwin-arm64/bin"
    )

    android = textwrap.dedent(f"""
       [settings]
       os=Android
       os.api_level=23
       arch=x86_64
       compiler=clang
       compiler.version=12
       compiler.libcxx=c++_shared
       build_type=Release
       [conf]
       tools.android:ndk_path={ndk_path}
       tools.build:compiler_executables = {{"c": "{bin_path}/x86_64-linux-android23-clang", "cpp": "{bin_path}/x86_64-linux-android23-clang++"}}
       """)

    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
        from conan.tools.build import check_min_cppstd
        class SDKConan(ConanFile):
            name = "sdk"
            version = "1.0"
            generators = "CMakeDeps", "VirtualBuildEnv"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "CMakeLists.txt"
            def layout(self):
                cmake_layout(self)
            def generate(self):
                tc = CMakeToolchain(self)
                tc.cache_variables["SDK_VERSION"] = str(self.version)
                tc.generate()
            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
    """)

    cmake = textwrap.dedent(f"""
        cmake_minimum_required(VERSION 3.23)
        project(sdk VERSION ${{SDK_VERSION}}.0 LANGUAGES NONE)
        message("sdk: ${{SDK_VERSION}}.0")
    """)

    c.save({"android": android,
            "conanfile.py": conanfile,
            "CMakeLists.txt": cmake,})
    # first run works ok
    c.run('build . --profile:host=android')
    assert 'sdk: 1.0.0' in c.out
    # in second run CMake says that you have changed variables that require your cache to be deleted.
    # and deletes the cache and fails
    c.run('build . --profile:host=android')
    assert 'VERSION ".0" format invalid.' not in c.out
    assert 'sdk: 1.0.0' in c.out


@pytest.mark.tool("cmake")
def test_cmake_toolchain_language_c():
    client = TestClient()

    conanfile = textwrap.dedent(r"""
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout

        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            generators = "CMakeToolchain"
            languages = "C"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        """)

    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(pkg NONE)
        """)

    client.save(
        {
            "conanfile.py": conanfile,
            "CMakeLists.txt": cmakelists,
        },
        clean_first=True,
    )

    if platform.system() == "Windows":
        # compiler.version=191 is already the default now
        client.run("build . -s compiler.cstd=11 -s compiler.version=191", assert_error=True)
        assert "The provided compiler.cstd=11 is not supported by msvc 191. Supported values are: []" \
               in client.out
    else:
        client.run("build . -s compiler.cppstd=11")
        # It doesn't fail


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
@pytest.mark.tool("cmake")
def test_cmaketoolchain_check_function_exists():
    """
    covers the problematic check_function_exists() CMake DISCOURAGED check, that can fail
    for Release configuration, due to CMake issues. This was broken when we tried to
    add the automatic CMAKE_TRY_COMPILE_CONFIGURATION in release cases, as CheckFunctionExists.c
    is optimized away or fails to compile in Release, but works in Debug.
    This test is here to capture this legacy and problematic use case NOT to recommended this
    as a good practice, rather then opposite, DONT DO IT
    """

    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain
        class Conan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            def generate(self):
                tc = CMakeToolchain(self)
                # This gets back to older default behavior
                # tc.blocks["try_compile"].values["config"] = None
                tc.generate()
            def build(self):
                CMake(self).configure()
        """)
    consumer = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello C)
        include(CheckFunctionExists)
        check_function_exists(pow HAVE_POW)
        if(NOT HAVE_POW)
            message(FATAL_ERROR "Not math!!!!!")
        endif()
       """)
    c.save({"conanfile.py": conanfile,
            "CMakeLists.txt": consumer})

    c.run("build . ")  # Release breaks the check
    assert "Looking for pow - found" in c.out
    # And it no longer crashes
