import json
import os
import platform
import re
import textwrap

import pytest

from conan.tools.cmake.presets import load_cmake_presets
from conan.tools.microsoft.visual import vcvars_command
from conans.model.recipe_ref import RecipeReference
from conan.test.assets.cmake import gen_cmakelists
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient, TurboTestClient
from conans.util.files import save, load, rmdir


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
    save(client.cache.new_config_path, "tools.cmake.cmaketoolchain:user_toolchain+=mytoolchain.cmake")

    client.save({"conanfile.py": conanfile})
    client.run("install .")
    toolchain = client.load("conan_toolchain.cmake")
    assert 'include("mytoolchain.cmake")' in toolchain


def test_cmake_toolchain_custom_toolchain():
    client = TestClient(path_with_spaces=False)
    conanfile = GenConanfile().with_settings("os", "compiler", "build_type", "arch").\
        with_generator("CMakeToolchain")
    save(client.cache.new_config_path, "tools.cmake.cmaketoolchain:toolchain_file=mytoolchain.cmake")

    client.save({"conanfile.py": conanfile})
    client.run("install .")
    assert not os.path.exists(os.path.join(client.current_folder, "conan_toolchain.cmake"))
    presets = load_cmake_presets(client.current_folder)
    assert "mytoolchain.cmake" in presets["configurePresets"][0]["toolchainFile"]
    assert "binaryDir" in presets["configurePresets"][0]


@pytest.mark.skipif(platform.system() != "Darwin",
                    reason="Single config test, Linux CI still without 3.23")
@pytest.mark.tool("cmake", "3.23")
@pytest.mark.parametrize("existing_user_presets", [None, "user_provided", "conan_generated"])
def test_cmake_user_presets_load(existing_user_presets):
    """
    Test if the CMakeUserPresets.cmake is generated and use CMake to use it to verify the right
    syntax of generated CMakeUserPresets.cmake and CMakePresets.cmake. If the user already provided
    a CMakeUserPresets.cmake, leave the file untouched, and only generate or modify the file if
    the `conan` object exists in the `vendor` field.
    """
    t = TestClient()
    t.run("new -d name=mylib -d version=1.0 -f cmake_lib")
    t.run("create . -s:h build_type=Release")
    t.run("create . -s:h build_type=Debug")

    consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class Consumer(ConanFile):

            settings = "build_type", "os", "arch", "compiler"
            requires = "mylib/1.0"
            generators = "CMakeToolchain", "CMakeDeps"

            def layout(self):
                cmake_layout(self)

    """)

    cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.1)
        project(PackageTest CXX)
        find_package(mylib REQUIRED CONFIG)
        """)

    user_presets = None
    if existing_user_presets == "user_provided":
        user_presets = "{}"
    elif existing_user_presets == "conan_generated":
        user_presets = '{ "vendor": {"conan": {} } }'

    files_to_save = {"conanfile.py": consumer, "CMakeLists.txt": cmakelist}

    if user_presets:
        files_to_save['CMakeUserPresets.json'] = user_presets
    t.save(files_to_save, clean_first=True)
    t.run("install . -s:h build_type=Debug -g CMakeToolchain")
    t.run("install . -s:h build_type=Release -g CMakeToolchain")

    user_presets_path = os.path.join(t.current_folder, "CMakeUserPresets.json")
    assert os.path.exists(user_presets_path)

    user_presets_data = json.loads(load(user_presets_path))
    if existing_user_presets == "user_provided":
        assert not user_presets_data
    else:
        assert "include" in user_presets_data.keys()

    if existing_user_presets is None:
        t.run_command("cmake . --preset conan-release")
        assert 'CMAKE_BUILD_TYPE="Release"' in t.out
        t.run_command("cmake . --preset conan-debug")
        assert 'CMAKE_BUILD_TYPE="Debug"' in t.out


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
       set(CMAKE_CXX_COMPILER_WORKS 1)
       set(CMAKE_CXX_ABI_COMPILED 1)
       project(MyHello CXX)

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
    ref = RecipeReference.loads("zlib/1.2.11")
    client = TurboTestClient()
    client.run("new cmake_lib -d name=zlib -d version=1.2.11")
    cf = client.load("conanfile.py")
    pref = client.create(ref, conanfile=cf)
    p_folder = client.get_latest_pkg_layout(pref).package()
    assert not os.path.exists(os.path.join(p_folder, "mylibs"))
    assert os.path.exists(os.path.join(p_folder, "lib"))

    # Edit the cpp.package.libdirs and check if the library is placed anywhere else
    cf = client.load("conanfile.py")
    cf = cf.replace("cmake_layout(self)",
                    'cmake_layout(self)\n        self.cpp.package.libdirs = ["mylibs"]')

    pref = client.create(ref, conanfile=cf)
    p_folder = client.get_latest_pkg_layout(pref).package()
    assert os.path.exists(os.path.join(p_folder, "mylibs"))
    assert not os.path.exists(os.path.join(p_folder, "lib"))

    b_folder = client.get_latest_pkg_layout(pref).build()
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


class TestAutoLinkPragma:
    # TODO: This is a CMakeDeps test, not a CMakeToolchain test, move it to the right place

    test_cf = textwrap.dedent("""
        import os

        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout, CMakeDeps
        from conan.tools.build import cross_building


        class HelloTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain", "VirtualBuildEnv", "VirtualRunEnv"
            apply_env = False
            test_type = "explicit"

            def generate(self):
                deps = CMakeDeps(self)
                deps.generate()

            def requirements(self):
                self.requires(self.tested_reference_str)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def layout(self):
                cmake_layout(self)

            def test(self):
                if not cross_building(self):
                    cmd = os.path.join(self.cpp.build.bindirs[0], "example")
                    self.run(cmd, env="conanrun")
        """)

    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Visual Studio")
    @pytest.mark.tool("cmake")
    def test_autolink_pragma_components(self):
        """https://github.com/conan-io/conan/issues/10837

        NOTE: At the moment the property cmake_set_interface_link_directories is only read at the
        global cppinfo, not in the components"""

        client = TestClient()
        client.run("new cmake_lib -d name=hello -d version=1.0")
        cf = client.load("conanfile.py")
        cf = cf.replace('self.cpp_info.libs = ["hello"]', """
            self.cpp_info.components['my_component'].includedirs.append('include')
            self.cpp_info.components['my_component'].libdirs.append('lib')
            self.cpp_info.components['my_component'].libs = []
            self.cpp_info.set_property("cmake_set_interface_link_directories", True)
        """)
        hello_h = client.load("include/hello.h")
        hello_h = hello_h.replace("#define HELLO_EXPORT __declspec(dllexport)",
                                  '#define HELLO_EXPORT __declspec(dllexport)\n'
                                  '#pragma comment(lib, "hello")')

        test_cmakelist = client.load("test_package/CMakeLists.txt")
        test_cmakelist = test_cmakelist.replace("target_link_libraries(example hello::hello)",
                                                "target_link_libraries(example hello::my_component)")
        client.save({"conanfile.py": cf,
                     "include/hello.h": hello_h,
                     "test_package/CMakeLists.txt": test_cmakelist,
                     "test_package/conanfile.py": self.test_cf})

        client.run("create .")

    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Visual Studio")
    @pytest.mark.tool("cmake")
    def test_autolink_pragma_without_components(self):
        """https://github.com/conan-io/conan/issues/10837"""
        client = TestClient()
        client.run("new cmake_lib -d name=hello -d version=1.0")
        cf = client.load("conanfile.py")
        cf = cf.replace('self.cpp_info.libs = ["hello"]', """
            self.cpp_info.includedirs.append('include')
            self.cpp_info.libdirs.append('lib')
            self.cpp_info.libs = []
            self.cpp_info.set_property("cmake_set_interface_link_directories", True)
        """)
        hello_h = client.load("include/hello.h")
        hello_h = hello_h.replace("#define HELLO_EXPORT __declspec(dllexport)",
                                  '#define HELLO_EXPORT __declspec(dllexport)\n'
                                  '#pragma comment(lib, "hello")')

        client.save({"conanfile.py": cf,
                     "include/hello.h": hello_h,
                     "test_package/conanfile.py": self.test_cf})

        client.run("create .")


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
    def test_cmake_toolchain_winsdk_version(self):
        # This test passes also with CMake 3.28, as long as cmake_minimum_required(VERSION 3.27)
        # is not defined
        client = TestClient(path_with_spaces=False)
        client.run("new cmake_lib -d name=hello -d version=0.1")
        cmake = client.load("CMakeLists.txt")
        cmake += 'message(STATUS "CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION = ' \
                 '${CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION}")'
        client.save({"CMakeLists.txt": cmake})
        client.run("create . -s arch=x86_64 -s compiler.version=193 "
                   "-c tools.microsoft:winsdk_version=8.1")
        assert "CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION = 8.1" in client.out
        assert "Conan toolchain: CMAKE_GENERATOR_PLATFORM=x64" in client.out
        assert "Conan toolchain: CMAKE_GENERATOR_PLATFORM=x64,version" not in client.out

    @pytest.mark.tool("cmake", "3.28")
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
        client.run("create . -s arch=x86_64 -s compiler.version=193 "
                   "-c tools.microsoft:winsdk_version=8.1 "
                   '-c tools.cmake.cmaketoolchain:generator="Visual Studio 17"')
        assert "CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION = 8.1" in client.out
        assert "Conan toolchain: CMAKE_GENERATOR_PLATFORM=x64,version=8.1" in client.out


@pytest.mark.tool("cmake", "3.23")
def test_cmake_presets_missing_option():
    client = TestClient(path_with_spaces=False)

    client.run("new cmake_exe -d name=hello -d version=0.1")
    settings_layout = '-c tools.cmake.cmake_layout:build_folder_vars=\'["options.missing"]\' ' \
                      '-c tools.cmake.cmaketoolchain:generator=Ninja'
    client.run("install . {}".format(settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, "build", "Release", "generators"))


@pytest.mark.tool("cmake", "3.23")
def test_cmake_presets_missing_setting():
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_exe -d name=hello -d version=0.1")
    settings_layout = '-c tools.cmake.cmake_layout:build_folder_vars=\'["settings.missing"]\' ' \
                      '-c tools.cmake.cmaketoolchain:generator=Ninja'
    client.run("install . {}".format(settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, "build", "Release", "generators"))


@pytest.mark.tool("cmake", "3.23")
def test_cmake_presets_multiple_settings_single_config():
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_exe -d name=hello -d version=0.1")
    settings_layout = '-c tools.cmake.cmake_layout:build_folder_vars=' \
                      '\'["settings.compiler", "settings.compiler.version", ' \
                      '   "settings.compiler.cppstd"]\''

    user_presets_path = os.path.join(client.current_folder, "CMakeUserPresets.json")

    # Check that all generated names are expected, both in the layout and in the Presets
    settings = "-s compiler=apple-clang -s compiler.libcxx=libc++ " \
               "-s compiler.version=12.0 -s compiler.cppstd=gnu17"
    client.run("install . {} {}".format(settings, settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, "build", "apple-clang-12.0-gnu17",
                                       "Release", "generators"))
    assert os.path.exists(user_presets_path)
    user_presets = json.loads(load(user_presets_path))
    assert len(user_presets["include"]) == 1
    presets = json.loads(client.load(user_presets["include"][0]))
    assert len(presets["configurePresets"]) == 1
    assert len(presets["buildPresets"]) == 1
    assert len(presets["testPresets"]) == 1
    assert presets["configurePresets"][0]["name"] == "conan-apple-clang-12.0-gnu17-release"
    assert presets["buildPresets"][0]["name"] == "conan-apple-clang-12.0-gnu17-release"
    assert presets["buildPresets"][0]["configurePreset"] == "conan-apple-clang-12.0-gnu17-release"
    assert presets["testPresets"][0]["name"] == "conan-apple-clang-12.0-gnu17-release"
    assert presets["testPresets"][0]["configurePreset"] == "conan-apple-clang-12.0-gnu17-release"

    # If we create the "Debug" one, it will be appended
    client.run("install . {} -s build_type=Debug {}".format(settings, settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, "build", "apple-clang-12.0-gnu17",
                                       "Release", "generators"))
    assert os.path.exists(user_presets_path)
    user_presets = json.loads(load(user_presets_path))
    assert len(user_presets["include"]) == 2
    presets = json.loads(client.load(user_presets["include"][0]))
    assert len(presets["configurePresets"]) == 1
    assert len(presets["buildPresets"]) == 1
    assert len(presets["testPresets"]) == 1
    assert presets["configurePresets"][0]["name"] == "conan-apple-clang-12.0-gnu17-release"
    assert presets["buildPresets"][0]["name"] == "conan-apple-clang-12.0-gnu17-release"
    assert presets["buildPresets"][0]["configurePreset"] == "conan-apple-clang-12.0-gnu17-release"
    assert presets["testPresets"][0]["name"] == "conan-apple-clang-12.0-gnu17-release"
    assert presets["testPresets"][0]["configurePreset"] == "conan-apple-clang-12.0-gnu17-release"

    presets = json.loads(client.load(user_presets["include"][1]))
    assert len(presets["configurePresets"]) == 1
    assert len(presets["buildPresets"]) == 1
    assert len(presets["testPresets"]) == 1
    assert presets["configurePresets"][0]["name"] == "conan-apple-clang-12.0-gnu17-debug"
    assert presets["buildPresets"][0]["name"] == "conan-apple-clang-12.0-gnu17-debug"
    assert presets["buildPresets"][0]["configurePreset"] == "conan-apple-clang-12.0-gnu17-debug"
    assert presets["testPresets"][0]["name"] == "conan-apple-clang-12.0-gnu17-debug"
    assert presets["testPresets"][0]["configurePreset"] == "conan-apple-clang-12.0-gnu17-debug"

    # But If we change, for example, the cppstd and the compiler version, the toolchain
    # and presets will be different, but it will be appended to the UserPresets.json
    settings = "-s compiler=apple-clang -s compiler.libcxx=libc++ " \
               "-s compiler.version=13 -s compiler.cppstd=gnu20"
    client.run("install . {} {}".format(settings, settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, "build", "apple-clang-13-gnu20",
                                       "Release", "generators"))
    assert os.path.exists(user_presets_path)
    user_presets = json.loads(load(user_presets_path))
    # The [0] is the apple-clang 12 the [1] is the apple-clang 13
    assert len(user_presets["include"]) == 3
    presets = json.loads(client.load(user_presets["include"][2]))
    assert len(presets["configurePresets"]) == 1
    assert len(presets["buildPresets"]) == 1
    assert len(presets["testPresets"]) == 1
    assert presets["configurePresets"][0]["name"] == "conan-apple-clang-13-gnu20-release"
    assert presets["buildPresets"][0]["name"] == "conan-apple-clang-13-gnu20-release"
    assert presets["buildPresets"][0]["configurePreset"] == "conan-apple-clang-13-gnu20-release"
    assert presets["testPresets"][0]["name"] == "conan-apple-clang-13-gnu20-release"
    assert presets["testPresets"][0]["configurePreset"] == "conan-apple-clang-13-gnu20-release"

    # We can build with cmake manually
    if platform.system() == "Darwin":
        client.run_command("cmake . --preset conan-apple-clang-12.0-gnu17-release")
        client.run_command("cmake --build --preset conan-apple-clang-12.0-gnu17-release")
        client.run_command("ctest --preset conan-apple-clang-12.0-gnu17-release")
        client.run_command("./build/apple-clang-12.0-gnu17/Release/hello")
        assert "Hello World Release!" in client.out
        assert "__cplusplus2017" in client.out

        client.run_command("cmake . --preset conan-apple-clang-12.0-gnu17-debug")
        client.run_command("cmake --build --preset conan-apple-clang-12.0-gnu17-debug")
        client.run_command("ctest --preset conan-apple-clang-12.0-gnu17-debug")
        client.run_command("./build/apple-clang-12.0-gnu17/Debug/hello")
        assert "Hello World Debug!" in client.out
        assert "__cplusplus2017" in client.out

        client.run_command("cmake . --preset conan-apple-clang-13-gnu20-release")
        client.run_command("cmake --build --preset conan-apple-clang-13-gnu20-release")
        client.run_command("ctest --preset conan-apple-clang-13-gnu20-release")
        client.run_command("./build/apple-clang-13-gnu20/Release/hello")
        assert "Hello World Release!" in client.out
        assert "__cplusplus2020" in client.out


@pytest.mark.parametrize("multiconfig", [True, False])
def test_cmake_presets_duplicated_install(multiconfig):
    # https://github.com/conan-io/conan/issues/11409
    """Only failed when using a multiconfig generator"""
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_exe -d name=hello -d version=0.1")
    settings = '-s compiler=gcc -s compiler.version=5 -s compiler.libcxx=libstdc++11 ' \
               '-c tools.cmake.cmake_layout:build_folder_vars=' \
               '\'["settings.compiler", "settings.compiler.version"]\' '
    if multiconfig:
        settings += '-c tools.cmake.cmaketoolchain:generator="Multi-Config"'
    client.run("install . {}".format(settings))
    client.run("install . {}".format(settings))
    if multiconfig:
        presets_path = os.path.join(client.current_folder, "build", "gcc-5", "generators",
                                    "CMakePresets.json")
    else:
        presets_path = os.path.join(client.current_folder, "build", "gcc-5", "Release", "generators",
                                    "CMakePresets.json")
    assert os.path.exists(presets_path)
    contents = json.loads(load(presets_path))
    assert len(contents["buildPresets"]) == 1
    assert len(contents["testPresets"]) == 1


def test_remove_missing_presets():
    # https://github.com/conan-io/conan/issues/11413
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_exe -d name=hello -d version=0.1")
    settings = '-s compiler=gcc -s compiler.version=5 -s compiler.libcxx=libstdc++11 ' \
               '-c tools.cmake.cmake_layout:build_folder_vars=' \
               '\'["settings.compiler", "settings.compiler.version"]\' '
    client.run("install . {}".format(settings))
    client.run("install . {} -s compiler.version=6".format(settings))

    presets_path_5 = os.path.join(client.current_folder, "build", "gcc-5")
    assert os.path.exists(presets_path_5)

    presets_path_6 = os.path.join(client.current_folder, "build", "gcc-6")
    assert os.path.exists(presets_path_6)

    rmdir(presets_path_5)

    # If we generate another configuration, the missing one (removed) for gcc-5 is not included
    client.run("install . {} -s compiler.version=11".format(settings))

    user_presets_path = os.path.join(client.current_folder, "CMakeUserPresets.json")
    assert os.path.exists(user_presets_path)

    contents = json.loads(load(user_presets_path))
    assert len(contents["include"]) == 2
    assert "gcc-6" in contents["include"][0]
    assert "gcc-11" in contents["include"][1]


@pytest.mark.tool("cmake", "3.23")
def test_cmake_presets_options_single_config():
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_lib -d name=hello -d version=0.1")
    conf_layout = '-c tools.cmake.cmake_layout:build_folder_vars=\'["settings.compiler",' \
                  '"settings.build_type", "options.shared"]\''

    default_compiler = {"Darwin": "apple-clang",
                        "Windows": "msvc",
                        "Linux": "gcc"}.get(platform.system())

    for shared in (True, False):
        client.run("install . {} -o shared={}".format(conf_layout, shared))
        shared_str = "shared" if shared else "static"
        assert os.path.exists(os.path.join(client.current_folder,
                                           "build", "{}-release-{}".format(default_compiler, shared_str),
                                           "generators"))

    client.run("install . {}".format(conf_layout))
    assert os.path.exists(os.path.join(client.current_folder,
                                       "build", "{}-release-static".format(default_compiler),
                                       "generators"))

    user_presets_path = os.path.join(client.current_folder, "CMakeUserPresets.json")
    assert os.path.exists(user_presets_path)

    # We can build with cmake manually
    if platform.system() == "Darwin":
        for shared in (True, False):
            shared_str = "shared" if shared else "static"
            client.run_command("cmake . --preset conan-apple-clang-release-{}".format(shared_str))
            client.run_command("cmake --build --preset conan-apple-clang-release-{}".format(shared_str))
            client.run_command("ctest --preset conan-apple-clang-release-{}".format(shared_str))
            the_lib = "libhello.a" if not shared else "libhello.dylib"
            path = os.path.join(client.current_folder,
                                "build", "apple-clang-release-{}".format(shared_str), the_lib)
            assert os.path.exists(path)


@pytest.mark.tool("cmake", "3.23")
@pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows")
def test_cmake_presets_multiple_settings_multi_config():
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_exe -d name=hello -d version=0.1")
    settings_layout = '-c tools.cmake.cmake_layout:build_folder_vars=' \
                      '\'["settings.compiler.runtime", "settings.compiler.cppstd"]\''

    user_presets_path = os.path.join(client.current_folder, "CMakeUserPresets.json")

    # Check that all generated names are expected, both in the layout and in the Presets
    settings = "-s compiler=msvc -s compiler.version=191 -s compiler.runtime=dynamic " \
               "-s compiler.cppstd=14"
    client.run("install . {} {}".format(settings, settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, "build", "dynamic-14", "generators"))
    assert os.path.exists(user_presets_path)
    user_presets = json.loads(load(user_presets_path))
    assert len(user_presets["include"]) == 1
    presets = json.loads(client.load(user_presets["include"][0]))
    assert len(presets["configurePresets"]) == 1
    assert len(presets["buildPresets"]) == 1
    assert len(presets["testPresets"]) == 1
    assert presets["configurePresets"][0]["name"] == "conan-dynamic-14"
    assert presets["buildPresets"][0]["name"] == "conan-dynamic-14-release"
    assert presets["buildPresets"][0]["configurePreset"] == "conan-dynamic-14"
    assert presets["testPresets"][0]["name"] == "conan-dynamic-14-release"
    assert presets["testPresets"][0]["configurePreset"] == "conan-dynamic-14"

    # If we create the "Debug" one, it has the same toolchain and preset file, that is
    # always multiconfig
    client.run("install . {} -s build_type=Debug {}".format(settings, settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, "build", "dynamic-14", "generators"))
    assert os.path.exists(user_presets_path)
    user_presets = json.loads(load(user_presets_path))
    assert len(user_presets["include"]) == 1
    presets = json.loads(client.load(user_presets["include"][0]))
    assert len(presets["configurePresets"]) == 1
    assert len(presets["buildPresets"]) == 2
    assert len(presets["testPresets"]) == 2
    assert presets["configurePresets"][0]["name"] == "conan-dynamic-14"
    assert presets["buildPresets"][0]["name"] == "conan-dynamic-14-release"
    assert presets["buildPresets"][1]["name"] == "conan-dynamic-14-debug"
    assert presets["buildPresets"][0]["configurePreset"] == "conan-dynamic-14"
    assert presets["buildPresets"][1]["configurePreset"] == "conan-dynamic-14"
    assert presets["testPresets"][0]["name"] == "conan-dynamic-14-release"
    assert presets["testPresets"][1]["name"] == "conan-dynamic-14-debug"
    assert presets["testPresets"][0]["configurePreset"] == "conan-dynamic-14"
    assert presets["testPresets"][1]["configurePreset"] == "conan-dynamic-14"

    # But If we change, for example, the cppstd and the compiler version, the toolchain
    # and presets will be different, but it will be appended to the UserPresets.json
    settings = "-s compiler=msvc -s compiler.version=191 -s compiler.runtime=static " \
               "-s compiler.cppstd=17"
    client.run("install . {} {}".format(settings, settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, "build", "static-17", "generators"))
    assert os.path.exists(user_presets_path)
    user_presets = json.loads(load(user_presets_path))
    # The [0] is the msvc dynamic/14 the [1] is the static/17
    assert len(user_presets["include"]) == 2
    presets = json.loads(client.load(user_presets["include"][1]))
    assert len(presets["configurePresets"]) == 1
    assert len(presets["buildPresets"]) == 1
    assert len(presets["testPresets"]) == 1
    assert presets["configurePresets"][0]["name"] == "conan-static-17"
    assert presets["buildPresets"][0]["name"] == "conan-static-17-release"
    assert presets["buildPresets"][0]["configurePreset"] == "conan-static-17"
    assert presets["testPresets"][0]["name"] == "conan-static-17-release"
    assert presets["testPresets"][0]["configurePreset"] == "conan-static-17"

    # We can build with cmake manually
    client.run_command("cmake . --preset conan-dynamic-14")

    client.run_command("cmake --build --preset conan-dynamic-14-release")
    client.run_command("ctest --preset conan-dynamic-14-release")
    client.run_command("build\\dynamic-14\\Release\\hello")
    assert "Hello World Release!" in client.out
    assert "MSVC_LANG2014" in client.out

    client.run_command("cmake --build --preset conan-dynamic-14-debug")
    client.run_command("ctest --preset conan-dynamic-14-debug")
    client.run_command("build\\dynamic-14\\Debug\\hello")
    assert "Hello World Debug!" in client.out
    assert "MSVC_LANG2014" in client.out

    client.run_command("cmake . --preset conan-static-17")

    client.run_command("cmake --build --preset conan-static-17-release")
    client.run_command("ctest --preset conan-static-17-release")
    client.run_command("build\\static-17\\Release\\hello")
    assert "Hello World Release!" in client.out
    assert "MSVC_LANG2017" in client.out


@pytest.mark.tool("cmake", "3.23")
@pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows")
# Test both with a local folder and an absolute folder
@pytest.mark.parametrize("build", ["mybuild", "temp"])
def test_cmake_presets_build_folder(build):
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_exe -d name=hello -d version=0.1")

    build = temp_folder() if build == "temp" else build
    settings_layout = f' -c tools.cmake.cmake_layout:build_folder="{build}" '\
                      '-c tools.cmake.cmake_layout:build_folder_vars=' \
                      '\'["settings.compiler.runtime", "settings.compiler.cppstd"]\''
    # But If we change, for example, the cppstd and the compiler version, the toolchain
    # and presets will be different, but it will be appended to the UserPresets.json
    settings = "-s compiler=msvc -s compiler.version=191 -s compiler.runtime=static " \
               "-s compiler.cppstd=17"
    client.run("install . {} {}".format(settings, settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, build, "static-17", "generators"))

    client.run_command("cmake . --preset conan-static-17")
    client.run_command("cmake --build --preset conan-static-17-release")
    client.run_command("ctest --preset conan-static-17-release")
    client.run_command(f"{build}\\static-17\\Release\\hello")
    assert "Hello World Release!" in client.out
    assert "MSVC_LANG2017" in client.out


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
        set(CMAKE_CXX_COMPILER_WORKS 1)
        project(app CXX)
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


@pytest.mark.tool("cmake", "3.23")
def test_cmake_presets_with_conanfile_txt():
    c = TestClient()

    c.run("new cmake_exe -d name=foo -d version=1.0")
    os.unlink(os.path.join(c.current_folder, "conanfile.py"))
    c.save({"conanfile.txt": textwrap.dedent("""
        [generators]
        CMakeToolchain

        [layout]
        cmake_layout
        """)})

    c.run("install .")
    c.run("install . -s build_type=Debug")

    if platform.system() != "Windows":
        c.run_command("cmake --preset conan-debug")
        c.run_command("cmake --build --preset conan-debug")
        c.run_command("ctest --preset conan-debug")
        c.run_command("./build/Debug/foo")
    else:
        c.run_command("cmake --preset conan-default")
        # this second called used to fail
        # https://github.com/conan-io/conan/issues/13792, CMake ignoring toolchain architecture
        # and toolset
        c.run_command("cmake --preset conan-default")
        c.run_command("cmake --build --preset conan-debug")
        c.run_command("ctest --preset conan-debug")
        c.run_command("build\\Debug\\foo")

    assert "Hello World Debug!" in c.out

    if platform.system() != "Windows":
        c.run_command("cmake --preset conan-release")
        c.run_command("cmake --build --preset conan-release")
        c.run_command("ctest --preset conan-release")
        c.run_command("./build/Release/foo")
    else:
        c.run_command("cmake --build --preset conan-release")
        c.run_command("ctest --preset conan-release")
        c.run_command("build\\Release\\foo")

    assert "Hello World Release!" in c.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows")
@pytest.mark.tool("ninja")
@pytest.mark.tool("cmake", "3.23")
def test_cmake_presets_with_conanfile_txt_ninja():
    c = TestClient()

    c.run("new cmake_exe -d name=foo -d version=1.0")
    os.unlink(os.path.join(c.current_folder, "conanfile.py"))
    c.save({"conanfile.txt": textwrap.dedent("""
        [generators]
        CMakeToolchain

        [layout]
        cmake_layout
        """)})

    conf = "-c tools.cmake.cmaketoolchain:generator=Ninja"
    c.run(f"install . {conf}")
    c.run(f"install . -s build_type=Debug {conf}")

    c.run_command("build\\Release\\generators\\conanbuild.bat && cmake --preset conan-release")
    c.run_command("build\\Release\\generators\\conanbuild.bat && cmake --preset conan-release")
    c.run_command("build\\Release\\generators\\conanbuild.bat && cmake --build --preset conan-release")
    c.run_command("build\\Release\\generators\\conanbuild.bat && ctest --preset conan-release")
    c.run_command("build\\Release\\foo")

    assert "Hello World Release!" in c.out


def test_cmake_presets_not_forbidden_build_type():
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
    set(CMAKE_CXX_COMPILER_WORKS 1)
    project(foo)
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
    set(CMAKE_CXX_COMPILER_WORKS 1)
    project(foo)
    if(NOT CMAKE_INSTALL_DATAROOTDIR)
        message(FATAL_ERROR "Cannot install stuff")
    endif()
    """

    client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmake, "my_license": "MIT"})
    client.run("create .", assert_error=True)
    assert "Cannot install stuff" in client.out


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
    project(pkg CXX)

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
    save(os.path.join(client.cache.profiles_path, "myprofile"), profile)
    save(os.path.join(client.cache.profiles_path, "myvars.cmake"), 'set(MY_USER_VAR1 "MYVALUE1")')
    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": cmake})
    client.run("build . -pr=myprofile")
    assert "-- MYVAR1 MYVALUE1!!" in client.out

    # Now test with the global.conf
    global_conf = 'tools.cmake.cmaketoolchain:user_toolchain=' \
                  '["{{conan_home_folder}}/my.cmake"]'
    save(client.cache.new_config_path, global_conf)
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


@pytest.mark.tool("cmake", "3.23")
class TestEnvironmentInPresets:
    @pytest.fixture(scope="class")
    def _init_client(self):
        c = TestClient()
        tool = textwrap.dedent(r"""
            import os
            from conan import ConanFile
            from conan.tools.files import chdir, save
            class Tool(ConanFile):
                version = "0.1"
                settings = "os", "compiler", "arch", "build_type"
                def package(self):
                    with chdir(self, self.package_folder):
                        save(self, f"bin/{{self.name}}.bat", f"@echo off\necho running: {{self.name}}/{{self.version}}")
                        save(self, f"bin/{{self.name}}.sh", f"echo running: {{self.name}}/{{self.version}}")
                        os.chmod(f"bin/{{self.name}}.sh", 0o777)
                def package_info(self):
                    self.buildenv_info.define("MY_BUILD_VAR", "MY_BUILDVAR_VALUE")
                    {}
            """)

        consumer = textwrap.dedent("""
            [tool_requires]
            mytool/0.1
            [test_requires]
            mytesttool/0.1
            [layout]
            cmake_layout
        """)

        test_env = textwrap.dedent("""
            #include <cstdlib>
            int main() {
                return std::getenv("MY_RUNVAR") ? 0 : 1;
            }
        """)

        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(MyProject)

            if(WIN32)
                set(MYTOOL_SCRIPT "mytool.bat")
            else()
                set(MYTOOL_SCRIPT "mytool.sh")
            endif()

            add_custom_target(run_mytool COMMAND ${MYTOOL_SCRIPT})

            function(check_and_report_variable var_name)
                set(var_value $ENV{${var_name}})
                if (var_value)
                    message("${var_name}:${var_value}")
                else()
                    message("${var_name} NOT FOUND")
                endif()
            endfunction()

            check_and_report_variable("MY_BUILD_VAR")
            check_and_report_variable("MY_RUNVAR")
            check_and_report_variable("MY_ENV_VAR")

            enable_testing()
            add_executable(test_env test_env.cpp)
            add_test(NAME TestRunEnv COMMAND test_env)
        """)

        c.save({"tool.py": tool.format(""),
                "test_tool.py": tool.format('self.runenv_info.define("MY_RUNVAR", "MY_RUNVAR_VALUE")'),
                "conanfile.txt": consumer,
                "CMakeLists.txt": cmakelists,
                "test_env.cpp": test_env})

        c.run("create tool.py --name=mytool")

        c.run("create test_tool.py --name=mytesttool")
        c.run("create test_tool.py --name=mytesttool -s build_type=Debug")

        yield c

    def test_add_env_to_presets(self, _init_client):
        c = _init_client

        # do a first conan install with env disabled just to test that the conf works
        c.run("install . -g CMakeToolchain -g CMakeDeps "
              "-c tools.cmake.cmaketoolchain:presets_environment=disabled")

        presets_path = os.path.join("build", "Release", "generators", "CMakePresets.json") \
            if platform.system() != "Windows" else os.path.join("build", "generators",
                                                                "CMakePresets.json")
        presets = json.loads(c.load(presets_path))

        assert presets["configurePresets"][0].get("env") is None

        c.run("install . -g CMakeToolchain -g CMakeDeps")
        c.run("install . -g CMakeToolchain -g CMakeDeps -s:h build_type=Debug")

        # test that the buildenv is correctly injected to configure and build steps
        # that the runenv is not injected to configure, but it is when running tests

        preset = "conan-default" if platform.system() == "Windows" else "conan-release"

        c.run_command(f"cmake --preset {preset}")
        assert "MY_BUILD_VAR:MY_BUILDVAR_VALUE" in c.out
        assert "MY_RUNVAR NOT FOUND" in c.out
        c.run_command("cmake --build --preset conan-release --target run_mytool --target test_env")
        assert "running: mytool/0.1" in c.out

        c.run_command("ctest --preset conan-release")
        assert "tests passed" in c.out

        if platform.system() != "Windows":
            c.run_command("cmake --preset conan-debug")
            assert "MY_BUILD_VAR:MY_BUILDVAR_VALUE" in c.out
            assert "MY_RUNVAR NOT FOUND" in c.out

        c.run_command("cmake --build --preset conan-debug --target run_mytool --target test_env")
        assert "running: mytool/0.1" in c.out

        c.run_command("ctest --preset conan-debug")
        assert "tests passed" in c.out

    def test_add_generate_env_to_presets(self, _init_client):
        c = _init_client

        consumer = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import cmake_layout, CMakeToolchain, CMakeDeps
            from conan.tools.env import VirtualBuildEnv, VirtualRunEnv, Environment

            class mypkgRecipe(ConanFile):
                name = "mypkg"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                tool_requires = "mytool/0.1"
                test_requires = "mytesttool/0.1"
                def layout(self):
                    cmake_layout(self)

                def generate(self):

                    buildenv = VirtualBuildEnv(self)
                    buildenv.environment().define("MY_BUILD_VAR", "MY_BUILDVAR_VALUE_OVERRIDEN")
                    buildenv.generate()

                    runenv = VirtualRunEnv(self)
                    runenv.environment().define("MY_RUN_VAR", "MY_RUNVAR_SET_IN_GENERATE")
                    runenv.generate()

                    env = Environment()
                    env.define("MY_ENV_VAR", "MY_ENV_VAR_VALUE")
                    env = env.vars(self)
                    env.save_script("other_env")

                    deps = CMakeDeps(self)
                    deps.generate()
                    tc = CMakeToolchain(self)
                    tc.presets_build_environment = buildenv.environment().compose_env(env)
                    tc.presets_run_environment = runenv.environment()
                    tc.generate()
        """)

        test_env = textwrap.dedent("""
            #include <string>
            int main() {
                return std::string(std::getenv("MY_RUNVAR"))=="MY_RUNVAR_SET_IN_GENERATE";
            }
        """)

        c.save({"conanfile.py": consumer,
                "test_env.cpp": test_env})

        c.run("install conanfile.py")

        preset = "conan-default" if platform.system() == "Windows" else "conan-release"

        c.run_command(f"cmake --preset {preset}")
        assert "MY_BUILD_VAR:MY_BUILDVAR_VALUE_OVERRIDEN" in c.out
        assert "MY_ENV_VAR:MY_ENV_VAR_VALUE" in c.out

        c.run_command("cmake --build --preset conan-release --target run_mytool --target test_env")
        assert "running: mytool/0.1" in c.out

        c.run_command(f"ctest --preset conan-release")
        assert "tests passed" in c.out


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
