import json
import os
import platform
import textwrap

import pytest

from conan.tools.cmake.presets import load_cmake_presets
from conan.tools.microsoft.visual import vcvars_command
from conans.client.tools import replace_in_file
from conans.model.ref import ConanFileReference
from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TurboTestClient
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
    if update is not None:  # Fullversion
        value = "version=14.{}{}".format(version[-1], update)
    else:
        value = "v14{}".format(version[-1])
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
    assert "binaryDir" not in presets["configurePresets"][0]


@pytest.mark.skipif(platform.system() != "Darwin",
                    reason="Single config test, Linux CI still without 3.23")
@pytest.mark.tool_cmake(version="3.23")
@pytest.mark.parametrize("existing_user_presets", [None, "user_provided", "conan_generated"])
@pytest.mark.parametrize("schema2", [True, False])
def test_cmake_user_presets_load(existing_user_presets, schema2):
    """
    Test if the CMakeUserPresets.cmake is generated and use CMake to use it to verify the right
    syntax of generated CMakeUserPresets.cmake and CMakePresets.cmake. If the user already provided
    a CMakeUserPresets.cmake, leave the file untouched, and only generate or modify the file if
    the `conan` object exists in the `vendor` field.
    """
    t = TestClient()
    t.run("new mylib/1.0 --template cmake_lib")
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

    if existing_user_presets == None:
        t.run_command("cmake . --preset release")
        assert 'CMAKE_BUILD_TYPE="Release"' in t.out
        t.run_command("cmake . --preset debug")
        assert 'CMAKE_BUILD_TYPE="Debug"' in t.out


def test_cmake_toolchain_user_toolchain_from_dep():
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile
        class Pkg(ConanFile):
            exports_sources = "*"
            def package(self):
                self.copy("*")
            def package_info(self):
                f = os.path.join(self.package_folder, "mytoolchain.cmake")
                self.conf_info.append("tools.cmake.cmaketoolchain:user_toolchain", f)
        """)
    client.save({"conanfile.py": conanfile,
                 "mytoolchain.cmake": 'message(STATUS "mytoolchain.cmake !!!running!!!")'})
    client.run("create . toolchain/0.1@")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
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
    client.run("create . pkg/0.1@")
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
        from conans import ConanFile
        class Pkg(ConanFile):
            exports_sources = "*"
            def package(self):
                self.copy("*")
            def package_info(self):
                f = os.path.join(self.package_folder, "mytoolchain.cmake")
                self.conf_info.append("tools.cmake.cmaketoolchain:user_toolchain", f)
        """)
    client.save({"conanfile.py": conanfile,
                 "mytoolchain.cmake": 'message(STATUS "mytoolchain1.cmake !!!running!!!")'})
    client.run("create . toolchain1/0.1@")
    client.save({"conanfile.py": conanfile,
                 "mytoolchain.cmake": 'message(STATUS "mytoolchain2.cmake !!!running!!!")'})
    client.run("create . toolchain2/0.1@")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake
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
    client.run("create . pkg/0.1@")
    assert "mytoolchain1.cmake !!!running!!!" in client.out
    assert "mytoolchain2.cmake !!!running!!!" in client.out


@pytest.mark.tool_cmake
def test_cmaketoolchain_no_warnings():
    """Make sure unitialized variables do not cause any warnings, passing -Werror=dev
    and --wanr-unitialized, calling "cmake" with conan_toolchain.cmake used to fail
    """
    # Issue https://github.com/conan-io/conan/issues/10288
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
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
    client.run_command("cmake . -DCMAKE_TOOLCHAIN_FILE=./conan_toolchain.cmake {}"
                       "-Werror=dev --warn-uninitialized".format(build_type))
    assert "Using Conan toolchain" in client.out
    # The real test is that there are no errors, it returns successfully


def test_install_output_directories():
    """
    If we change the libdirs of the cpp.package, as we are doing cmake.install, the output directory
    for the libraries is changed
    """
    ref = ConanFileReference.loads("zlib/1.2.11")
    client = TurboTestClient()
    client.run("new zlib/1.2.11 --template cmake_lib")
    cf = client.load("conanfile.py")
    pref = client.create(ref, conanfile=cf)
    p_folder = client.cache.package_layout(pref.ref).package(pref)
    assert not os.path.exists(os.path.join(p_folder, "mylibs"))
    assert os.path.exists(os.path.join(p_folder, "lib"))

    # Edit the cpp.package.libdirs and check if the library is placed anywhere else
    cf = client.load("conanfile.py")
    cf = cf.replace("cmake_layout(self)",
                    'cmake_layout(self)\n        self.cpp.package.libdirs = ["mylibs"]')

    pref = client.create(ref, conanfile=cf)
    p_folder = client.cache.package_layout(pref.ref).package(pref)
    assert os.path.exists(os.path.join(p_folder, "mylibs"))
    assert not os.path.exists(os.path.join(p_folder, "lib"))
    b_folder = client.cache.package_layout(pref.ref).build(pref)
    toolchain = client.load(os.path.join(b_folder, "build", "generators", "conan_toolchain.cmake"))
    assert 'set(CMAKE_INSTALL_LIBDIR "mylibs")' in toolchain


@pytest.mark.tool_cmake
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
                tc.preprocessor_definitions.release["escape_release"] = "release partially \"escaped\""
                tc.preprocessor_definitions.release["spaces_release"] = "release me you"
                tc.preprocessor_definitions.release["foobar_release"] = "release bazbuz"
                tc.preprocessor_definitions.release["answer_release"] = 42

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
    client.run("install . -pr=./profile -if=install")
    client.run("build . -if=install")
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

    client.run("install . -pr=./profile -if=install -s build_type=Debug")
    client.run("build . -if=install -s build_type=Debug")
    exe = "build/Debug/example" if platform.system() != "Windows" else r"build\Debug\example.exe"
    client.run_command(exe)
    assert 'escape_debug=debug partially "escaped"' in client.out
    assert 'spaces_debug=debug me you' in client.out
    assert 'foobar_debug=debug bazbuz' in client.out
    assert 'answer_debug=21' in client.out


class TestAutoLinkPragma:

    # Consumer test_package setting cmake_deps.set_interface_link_directories = True
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
                deps.set_interface_link_directories = True
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
    @pytest.mark.tool_cmake
    def test_autolink_pragma_components(self):
        """https://github.com/conan-io/conan/issues/10837

        NOTE: At the moment the property cmake_set_interface_link_directories is only read at the
        global cppinfo, not in the components"""

        client = TestClient()
        client.run("new hello/1.0 --template cmake_lib")
        cf = client.load("conanfile.py")
        cf = cf.replace('self.cpp_info.libs = ["hello"]', """
            self.cpp_info.components['my_component'].includedirs.append('include')
            self.cpp_info.components['my_component'].libdirs.append('lib')
            self.cpp_info.components['my_component'].libs = []
            self.cpp_info.set_property("cmake_set_interface_link_directories", True)
        """)
        hello_h = client.load("include/hello.h")
        hello_h = hello_h.replace("#define hello_EXPORT __declspec(dllexport)",
                                  '#define hello_EXPORT __declspec(dllexport)\n'
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
    @pytest.mark.tool_cmake
    def test_autolink_pragma_without_components(self):
        """https://github.com/conan-io/conan/issues/10837"""
        client = TestClient()
        client.run("new hello/1.0 --template cmake_lib")
        cf = client.load("conanfile.py")
        cf = cf.replace('self.cpp_info.libs = ["hello"]', """
            self.cpp_info.includedirs.append('include')
            self.cpp_info.libdirs.append('lib')
            self.cpp_info.libs = []
            self.cpp_info.set_property("cmake_set_interface_link_directories", True)
        """)
        hello_h = client.load("include/hello.h")
        hello_h = hello_h.replace("#define hello_EXPORT __declspec(dllexport)",
                                  '#define hello_EXPORT __declspec(dllexport)\n'
                                  '#pragma comment(lib, "hello")')

        client.save({"conanfile.py": cf,
                     "include/hello.h": hello_h,
                     "test_package/conanfile.py": self.test_cf})

        client.run("create .")


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
def test_cmake_toolchain_runtime_types():
    # everything works with the default cmake_minimum_required version 3.15 in the template
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=cmake_lib")
    client.run("install . -s compiler.runtime=MTd -s build_type=Debug")
    client.run("build .")

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
    client.run("new hello/0.1 --template=cmake_lib")
    replace_in_file(os.path.join(client.current_folder, "CMakeLists.txt"),
                    'cmake_minimum_required(VERSION 3.15)',
                    'cmake_minimum_required(VERSION 3.1)'
                    , output=client.out)

    client.run("install . -s compiler.runtime=MTd -s build_type=Debug")
    client.run("build .")

    vcvars = vcvars_command(version="15", architecture="x64")
    lib = os.path.join(client.current_folder, "build", "Debug", "hello.lib")
    dumpbind_cmd = '{} && dumpbin /directives "{}"'.format(vcvars, lib)
    client.run_command(dumpbind_cmd)
    assert "LIBCMTD" in client.out


@pytest.mark.tool_cmake(version="3.23")
def test_cmake_presets_missing_option():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=cmake_exe")
    settings_layout = '-c tools.cmake.cmake_layout:build_folder_vars=' \
                      '\'["options.missing"]\''
    client.run("install . {}".format(settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, "build", "generators"))


@pytest.mark.tool_cmake(version="3.23")
def test_cmake_presets_missing_setting():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=cmake_exe")
    settings_layout = '-c tools.cmake.cmake_layout:build_folder_vars=' \
                      '\'["settings.missing"]\''
    client.run("install . {}".format(settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, "build", "generators"))


@pytest.mark.tool_cmake(version="3.23")
def test_cmake_presets_multiple_settings_single_config():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=cmake_exe")
    settings_layout = '-c tools.cmake.cmake_layout:build_folder_vars=' \
                      '\'["settings.compiler", "settings.compiler.version", ' \
                      '   "settings.compiler.cppstd"]\''

    user_presets_path = os.path.join(client.current_folder, "CMakeUserPresets.json")

    # Check that all generated names are expected, both in the layout and in the Presets
    settings = "-s compiler=apple-clang -s compiler.libcxx=libc++ " \
               "-s compiler.version=12.0 -s compiler.cppstd=gnu17"
    client.run("install . {} {}".format(settings, settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, "build", "apple-clang-12.0-gnu17",
                                       "generators"))
    assert os.path.exists(user_presets_path)
    user_presets = json.loads(load(user_presets_path))
    assert len(user_presets["include"]) == 1
    presets = json.loads(load(user_presets["include"][0]))
    assert len(presets["configurePresets"]) == 1
    assert len(presets["buildPresets"]) == 1
    assert presets["configurePresets"][0]["name"] == "apple-clang-12.0-gnu17-release"
    assert presets["buildPresets"][0]["name"] == "apple-clang-12.0-gnu17-release"
    assert presets["buildPresets"][0]["configurePreset"] == "apple-clang-12.0-gnu17-release"

    # If we create the "Debug" one, it has the same toolchain and preset file, that is
    # always multiconfig
    client.run("install . {} -s build_type=Debug {}".format(settings, settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, "build", "apple-clang-12.0-gnu17", "generators"))
    assert os.path.exists(user_presets_path)
    user_presets = json.loads(load(user_presets_path))
    assert len(user_presets["include"]) == 1
    presets = json.loads(load(user_presets["include"][0]))
    assert len(presets["configurePresets"]) == 2
    assert len(presets["buildPresets"]) == 2
    assert presets["configurePresets"][0]["name"] == "apple-clang-12.0-gnu17-release"
    assert presets["configurePresets"][1]["name"] == "apple-clang-12.0-gnu17-debug"
    assert presets["buildPresets"][0]["name"] == "apple-clang-12.0-gnu17-release"
    assert presets["buildPresets"][1]["name"] == "apple-clang-12.0-gnu17-debug"
    assert presets["buildPresets"][0]["configurePreset"] == "apple-clang-12.0-gnu17-release"
    assert presets["buildPresets"][1]["configurePreset"] == "apple-clang-12.0-gnu17-debug"

    # But If we change, for example, the cppstd and the compiler version, the toolchain
    # and presets will be different, but it will be appended to the UserPresets.json
    settings = "-s compiler=apple-clang -s compiler.libcxx=libc++ " \
               "-s compiler.version=13 -s compiler.cppstd=gnu20"
    client.run("install . {} {}".format(settings, settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, "build", "apple-clang-13-gnu20",
                                       "generators"))
    assert os.path.exists(user_presets_path)
    user_presets = json.loads(load(user_presets_path))
    # The [0] is the apple-clang 12 the [1] is the apple-clang 13
    assert len(user_presets["include"]) == 2
    presets = json.loads(load(user_presets["include"][1]))
    assert len(presets["configurePresets"]) == 1
    assert len(presets["buildPresets"]) == 1
    assert presets["configurePresets"][0]["name"] == "apple-clang-13-gnu20-release"
    assert presets["buildPresets"][0]["name"] == "apple-clang-13-gnu20-release"
    assert presets["buildPresets"][0]["configurePreset"] == "apple-clang-13-gnu20-release"

    # We can build with cmake manually
    if platform.system() == "Darwin":
        client.run_command("cmake . --preset apple-clang-12.0-gnu17-release")
        client.run_command("cmake --build --preset apple-clang-12.0-gnu17-release")
        client.run_command("./build/apple-clang-12.0-gnu17/Release/hello")
        assert "Hello World Release!" in client.out
        assert "__cplusplus2017" in client.out

        client.run_command("cmake . --preset apple-clang-12.0-gnu17-debug")
        client.run_command("cmake --build --preset apple-clang-12.0-gnu17-debug")
        client.run_command("./build/apple-clang-12.0-gnu17/Debug/hello")
        assert "Hello World Debug!" in client.out
        assert "__cplusplus2017" in client.out

        client.run_command("cmake . --preset apple-clang-13-gnu20-release")
        client.run_command("cmake --build --preset apple-clang-13-gnu20-release")
        client.run_command("./build/apple-clang-13-gnu20/Release/hello")
        assert "Hello World Release!" in client.out
        assert "__cplusplus2020" in client.out


@pytest.mark.parametrize("multiconfig", [True, False])
def test_cmake_presets_duplicated_install(multiconfig):
    # https://github.com/conan-io/conan/issues/11409
    """Only failed when using a multiconfig generator"""
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=cmake_exe")
    settings = '-s compiler=gcc -s compiler.version=5 -s compiler.libcxx=libstdc++11 ' \
               '-c tools.cmake.cmake_layout:build_folder_vars=' \
               '\'["settings.compiler", "settings.compiler.version"]\' '
    if multiconfig:
        settings += '-c tools.cmake.cmaketoolchain:generator="Multi-Config"'
    client.run("install . {}".format(settings))
    client.run("install . {}".format(settings))
    presets_path = os.path.join(client.current_folder, "build", "gcc-5", "generators",
                                "CMakePresets.json")
    assert os.path.exists(presets_path)
    contents = json.loads(load(presets_path))
    assert len(contents["buildPresets"]) == 1


def test_remove_missing_presets():
    # https://github.com/conan-io/conan/issues/11413
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=cmake_exe")
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


@pytest.mark.tool_cmake(version="3.23")
def test_cmake_presets_options_single_config():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=cmake_lib")
    conf_layout = '-c tools.cmake.cmake_layout:build_folder_vars=\'["settings.compiler", ' \
                  '"options.shared"]\''

    default_compiler = {"Darwin": "apple-clang",
                        "Windows": "visual studio",  # FIXME:  replace it with 'msvc' in develop2
                        "Linux": "gcc"}.get(platform.system())

    for shared in (True, False):
        client.run("install . {} -o shared={}".format(conf_layout, shared))
        shared_str = "shared_true" if shared else "shared_false"
        assert os.path.exists(os.path.join(client.current_folder,
                                           "build", "{}-{}".format(default_compiler, shared_str),
                                           "generators"))

    client.run("install . {}".format(conf_layout))
    assert os.path.exists(os.path.join(client.current_folder,
                                       "build", "{}-shared_false".format(default_compiler),
                                       "generators"))

    user_presets_path = os.path.join(client.current_folder, "CMakeUserPresets.json")
    assert os.path.exists(user_presets_path)

    # We can build with cmake manually
    if platform.system() == "Darwin":
        for shared in (True, False):
            shared_str = "shared_true" if shared else "shared_false"
            client.run_command("cmake . --preset apple-clang-{}-release".format(shared_str))
            client.run_command("cmake --build --preset apple-clang-{}-release".format(shared_str))
            the_lib = "libhello.a" if not shared else "libhello.dylib"
            path = os.path.join(client.current_folder,
                                "build", "apple-clang-{}".format(shared_str), "release", the_lib)
            assert os.path.exists(path)


@pytest.mark.tool_cmake(version="3.23")
@pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows")
def test_cmake_presets_multiple_settings_multi_config():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=cmake_exe")
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
    presets = json.loads(load(user_presets["include"][0]))
    assert len(presets["configurePresets"]) == 1
    assert len(presets["buildPresets"]) == 1
    assert presets["configurePresets"][0]["name"] == "dynamic-14"
    assert presets["buildPresets"][0]["name"] == "dynamic-14-release"
    assert presets["buildPresets"][0]["configurePreset"] == "dynamic-14"

    # If we create the "Debug" one, it has the same toolchain and preset file, that is
    # always multiconfig
    client.run("install . {} -s build_type=Debug {}".format(settings, settings_layout))
    assert os.path.exists(os.path.join(client.current_folder, "build", "dynamic-14", "generators"))
    assert os.path.exists(user_presets_path)
    user_presets = json.loads(load(user_presets_path))
    assert len(user_presets["include"]) == 1
    presets = json.loads(load(user_presets["include"][0]))
    assert len(presets["configurePresets"]) == 1
    assert len(presets["buildPresets"]) == 2
    assert presets["configurePresets"][0]["name"] == "dynamic-14"
    assert presets["buildPresets"][0]["name"] == "dynamic-14-release"
    assert presets["buildPresets"][1]["name"] == "dynamic-14-debug"
    assert presets["buildPresets"][0]["configurePreset"] == "dynamic-14"
    assert presets["buildPresets"][1]["configurePreset"] == "dynamic-14"

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
    presets = json.loads(load(user_presets["include"][1]))
    assert len(presets["configurePresets"]) == 1
    assert len(presets["buildPresets"]) == 1
    assert presets["configurePresets"][0]["name"] == "static-17"
    assert presets["buildPresets"][0]["name"] == "static-17-release"
    assert presets["buildPresets"][0]["configurePreset"] == "static-17"

    # We can build with cmake manually
    client.run_command("cmake . --preset dynamic-14")

    client.run_command("cmake --build --preset dynamic-14-release")
    client.run_command("build\\dynamic-14\\Release\\hello")
    assert "Hello World Release!" in client.out
    assert "MSVC_LANG2014" in client.out

    client.run_command("cmake --build --preset dynamic-14-debug")
    client.run_command("build\\dynamic-14\\Debug\\hello")
    assert "Hello World Debug!" in client.out
    assert "MSVC_LANG2014" in client.out

    client.run_command("cmake . --preset static-17")

    client.run_command("cmake --build --preset static-17-release")
    client.run_command("build\\static-17\\Release\\hello")
    assert "Hello World Release!" in client.out
    assert "MSVC_LANG2017" in client.out


@pytest.mark.tool_cmake(version="3.23")
def test_max_schema_version2_build():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=cmake_exe")
    configs = ["-c tools.cmake.cmaketoolchain.presets:max_schema_version=2"]
    client.run("install . {} -s compiler.cppstd=14".format(" ".join(configs)))
    client.run("build .")


@pytest.mark.tool_cmake(version="3.23")
def test_user_presets_version2():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=cmake_exe")
    configs = ["-c tools.cmake.cmaketoolchain.presets:max_schema_version=2 ",
               "-c tools.cmake.cmake_layout:build_folder_vars='[\"settings.compiler.cppstd\"]'"]
    client.run("install . {} -s compiler.cppstd=14".format(" ".join(configs)))
    client.run("install . {} -s compiler.cppstd=17".format(" ".join(configs)))
    client.run("install . {} -s compiler.cppstd=20".format(" ".join(configs)))

    if platform.system() == "Windows":
        client.run_command("cmake . --preset 14")
        client.run_command("cmake --build --preset 14-release")
        client.run_command(r"build\14\Release\hello.exe")
    else:
        client.run_command("cmake . --preset 14-release")
        client.run_command("cmake --build --preset 14-release")
        client.run_command("./build/14/Release/hello")

    assert "Hello World Release!" in client.out

    if platform.system() != "Windows":
        assert "__cplusplus2014" in client.out
    else:
        assert "MSVC_LANG2014" in client.out

    if platform.system() == "Windows":
        client.run_command("cmake . --preset 17")
        client.run_command("cmake --build --preset 17-release")
        client.run_command(r"build\17\Release\hello.exe")
    else:
        client.run_command("cmake . --preset 17-release")
        client.run_command("cmake --build --preset 17-release")
        client.run_command("./build/17/Release/hello")

    assert "Hello World Release!" in client.out
    if platform.system() != "Windows":
        assert "__cplusplus2017" in client.out
    else:
        assert "MSVC_LANG2017" in client.out


@pytest.mark.tool_cmake
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
    client.run("create . app/1.0@ -c tools.build:sysroot='{}'".format(fake_sysroot))
    assert "sysroot: '{}'".format(output_fake_sysroot) in client.out

    # set in a block instead of using conf
    set_sysroot_in_block = 'tc.blocks["generic_system"].values["cmake_sysroot"] = "{}"'.format(output_fake_sysroot)
    client.save({
        "conanfile.py": conanfile.format(set_sysroot_in_block),
    })
    client.run("create . app/1.0@")
    assert "sysroot: '{}'".format(output_fake_sysroot) in client.out


# FIXME: DEVELOP2: @pytest.mark.tool("cmake", "3.23")
@pytest.mark.tool_cmake(version="3.23")
def test_cmake_presets_with_conanfile_txt():
    c = TestClient()

    # FIXME: DEVELOP 2: c.run("new cmake_exe -d name=foo -d version=1.0")
    c.run("new foo/1.0 --template cmake_exe")
    os.unlink(os.path.join(c.current_folder, "conanfile.py"))
    c.save({"conanfile.txt": textwrap.dedent("""

    [generators]
    CMakeToolchain

    [layout]
    cmake_layout

    """)})

    c.run("install .")
    c.run("install . -s build_type=Debug")
    assert os.path.exists(os.path.join(c.current_folder, "CMakeUserPresets.json"))
    presets_path = os.path.join(c.current_folder, "build", "generators", "CMakePresets.json")
    assert os.path.exists(presets_path)

    if platform.system() != "Windows":
        c.run_command("cmake --preset debug")
        c.run_command("cmake --build --preset debug")
        c.run_command("./build/Debug/foo")
    else:
        c.run_command("cmake --preset default")
        c.run_command("cmake --build --preset debug")
        c.run_command("build\\Debug\\foo")

    assert "Hello World Debug!" in c.out

    if platform.system() != "Windows":
        c.run_command("cmake --preset release")
        c.run_command("cmake --build --preset release")
        c.run_command("./build/Release/foo")
    else:
        c.run_command("cmake --build --preset release")
        c.run_command("build\\Release\\foo")

    assert "Hello World Release!" in c.out


def test_cmake_presets_forbidden_build_type():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template cmake_exe")
    # client.run("new cmake_exe -d name=hello -d version=0.1")
    settings_layout = '-c tools.cmake.cmake_layout:build_folder_vars=' \
                      '\'["options.missing", "settings.build_type"]\''
    client.run("install . {}".format(settings_layout), assert_error=True)
    assert "Error, don't include 'settings.build_type' in the " \
           "'tools.cmake.cmake_layout:build_folder_vars' conf" in client.out


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
