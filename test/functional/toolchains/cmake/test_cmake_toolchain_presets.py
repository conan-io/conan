import json
import os
import platform
import textwrap

import pytest

from conan.internal.util.files import load, rmdir
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conan.tools.cmake.presets import load_cmake_presets


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
                                           "build", f"{default_compiler}-release-{shared_str}",
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
            client.run_command(f"cmake . --preset conan-apple-clang-release-{shared_str}")
            client.run_command(f"cmake --build --preset conan-apple-clang-release-{shared_str}")
            client.run_command(f"ctest --preset conan-apple-clang-release-{shared_str}")
            the_lib = "libhello.a" if not shared else "libhello.dylib"
            path = os.path.join(client.current_folder,
                                "build", "apple-clang-release-{}".format(shared_str), the_lib)
            assert os.path.exists(path)


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
    c.run_command("build\\Release\\generators\\conanbuild.bat "
                  "&& cmake --build --preset conan-release")
    c.run_command("build\\Release\\generators\\conanbuild.bat && ctest --preset conan-release")
    c.run_command("build\\Release\\foo")

    assert "Hello World Release!" in c.out


def test_cmake_toolchain_custom_toolchain():
    client = TestClient(path_with_spaces=False)
    conanfile = GenConanfile().with_settings("os", "compiler", "build_type", "arch").\
        with_generator("CMakeToolchain")
    client.save_home({"global.conf": "tools.cmake.cmaketoolchain:toolchain_file=mytoolchain.cmake"})

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
        project(PackageTest NONE)
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
                        v = f"{{self.name}}/{{self.version}}"
                        save(self, f"bin/{{self.name}}.bat", f"@echo off\necho running: {{v}}")
                        save(self, f"bin/{{self.name}}.sh", f"echo running: {{v}}")
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
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            cmake_minimum_required(VERSION 3.15)
            project(MyProject CXX)

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
                "test_tool.py":
                    tool.format('self.runenv_info.define("MY_RUNVAR", "MY_RUNVAR_VALUE")'),
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
