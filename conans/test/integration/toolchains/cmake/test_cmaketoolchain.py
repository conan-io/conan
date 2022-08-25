import json
import os
import platform
import textwrap

import pytest
from mock import mock

from conan.tools.cmake.presets import load_cmake_presets
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import rmdir


def test_cross_build():
    windows_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        """)
    rpi_profile = textwrap.dedent("""
        [settings]
        os=Linux
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        arch=armv8
        build_type=Release
        """)

    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                "rpi": rpi_profile,
                 "windows": windows_profile})
    client.run("install . --profile:build=windows --profile:host=rpi")
    toolchain = client.load("conan_toolchain.cmake")

    assert "set(CMAKE_SYSTEM_NAME Linux)" in toolchain
    assert "set(CMAKE_SYSTEM_PROCESSOR armv8)" in toolchain


def test_cross_build_user_toolchain():
    # When a user_toolchain is defined in [conf], CMakeToolchain will not generate anything
    # for cross-build
    windows_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        """)
    rpi_profile = textwrap.dedent("""
        [settings]
        os=Linux
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        arch=armv8
        build_type=Release
        [conf]
        tools.cmake.cmaketoolchain:user_toolchain+=rpi_toolchain.cmake
        """)

    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                "rpi": rpi_profile,
                 "windows": windows_profile})
    client.run("install . --profile:build=windows --profile:host=rpi")
    toolchain = client.load("conan_toolchain.cmake")

    assert "CMAKE_SYSTEM_NAME " not in toolchain
    assert "CMAKE_SYSTEM_PROCESSOR" not in toolchain


def test_no_cross_build():
    windows_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        build_type=Release
        """)

    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                 "windows": windows_profile})
    client.run("install . --profile:build=windows --profile:host=windows")
    toolchain = client.load("conan_toolchain.cmake")

    assert "CMAKE_SYSTEM_NAME " not in toolchain
    assert "CMAKE_SYSTEM_PROCESSOR" not in toolchain


def test_cross_arch():
    # Compiling to 32bits in an architecture that runs is not full cross-compiling
    build_profile = textwrap.dedent("""
        [settings]
        os=Linux
        arch=x86_64
        """)
    profile_arm = textwrap.dedent("""
        [settings]
        os=Linux
        arch=armv8
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        build_type=Release
        """)

    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                "linux64": build_profile,
                 "linuxarm": profile_arm})
    client.run("install . --profile:build=linux64 --profile:host=linuxarm")
    toolchain = client.load("conan_toolchain.cmake")

    assert "set(CMAKE_SYSTEM_NAME Linux)" in toolchain
    assert "set(CMAKE_SYSTEM_PROCESSOR armv8)" in toolchain


def test_no_cross_build_arch():
    # Compiling to 32bits in an architecture that runs is not full cross-compiling
    build_profile = textwrap.dedent("""
        [settings]
        os=Linux
        arch=x86_64
        """)
    profile_32 = textwrap.dedent("""
        [settings]
        os=Linux
        arch=x86
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        build_type=Release
        """)

    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                "linux64": build_profile,
                 "linux32": profile_32})
    client.run("install . --profile:build=linux64 --profile:host=linux32")
    toolchain = client.load("conan_toolchain.cmake")

    assert "CMAKE_SYSTEM_NAME" not in toolchain
    assert "CMAKE_SYSTEM_PROCESSOR " not in toolchain


def test_cross_build_conf():
    windows_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        """)
    rpi_profile = textwrap.dedent("""
        [settings]
        os=Linux
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        arch=armv8
        build_type=Release

        [conf]
        tools.cmake.cmaketoolchain:system_name = Custom
        tools.cmake.cmaketoolchain:system_version= 42
        tools.cmake.cmaketoolchain:system_processor = myarm
        """)

    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                "rpi": rpi_profile,
                 "windows": windows_profile})
    client.run("install . --profile:build=windows --profile:host=rpi")
    toolchain = client.load("conan_toolchain.cmake")

    assert "set(CMAKE_SYSTEM_NAME Custom)" in toolchain
    assert "set(CMAKE_SYSTEM_VERSION 42)" in toolchain
    assert "set(CMAKE_SYSTEM_PROCESSOR myarm)" in toolchain


def test_find_builddirs():
    client = TestClient()
    conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile
            from conan.tools.cmake import CMakeToolchain

            class Conan(ConanFile):
                settings = "os", "arch", "compiler", "build_type"

                def package_info(self):
                    self.cpp_info.builddirs = ["/path/to/builddir"]
            """)
    client.save({"conanfile.py": conanfile})
    client.run("create . dep/1.0@")

    conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile
            from conan.tools.cmake import CMakeToolchain

            class Conan(ConanFile):
                name = "mydep"
                version = "1.0"
                settings = "os", "arch", "compiler", "build_type"
                requires = "dep/1.0@"

                def generate(self):
                    cmake = CMakeToolchain(self)
                    {}
                    cmake.generate()
            """)

    client.save({"conanfile.py": conanfile})
    client.run("install . ")
    with open(os.path.join(client.current_folder, "conan_toolchain.cmake")) as f:
        contents = f.read()
        assert "/path/to/builddir" in contents


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_cmaketoolchain_cmake_system_processor_cross_apple():
    """
    https://github.com/conan-io/conan/pull/10434
    CMAKE_SYSTEM_PROCESSOR was not set when cross-building in Mac
    """
    client = TestClient()
    client.save({"hello.py": GenConanfile().with_name("hello")
                                           .with_version("1.0")
                                           .with_settings("os", "arch", "compiler", "build_type")})
    profile_ios = textwrap.dedent("""
        include(default)
        [settings]
        os=iOS
        os.version=15.4
        os.sdk=iphoneos
        os.sdk_version=15.0
        arch=armv8
    """)
    client.save({"profile_ios": profile_ios})
    client.run("install hello.py -pr:h=./profile_ios -pr:b=default -g CMakeToolchain")
    toolchain = client.load("conan_toolchain.cmake")
    assert "set(CMAKE_SYSTEM_NAME iOS)" in toolchain
    assert "set(CMAKE_SYSTEM_VERSION 15.0)" in toolchain
    assert "set(CMAKE_SYSTEM_PROCESSOR arm64)" in toolchain


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_apple_vars_overwrite_user_conf():
    """
        tools.cmake.cmaketoolchain:system_name and tools.cmake.cmaketoolchain:system_version
        will be overwritten by the apple block
    """
    client = TestClient()
    client.save({"hello.py": GenConanfile().with_name("hello")
                                           .with_version("1.0")
                                           .with_settings("os", "arch", "compiler", "build_type")})
    profile_ios = textwrap.dedent("""
        include(default)
        [settings]
        os=iOS
        os.version=15.4
        os.sdk=iphoneos
        os.sdk_version=15.0
        arch=armv8
    """)
    client.save({"profile_ios": profile_ios})
    client.run("install hello.py -pr:h=./profile_ios -pr:b=default -g CMakeToolchain "
               "-c tools.cmake.cmaketoolchain:system_name=tvOS "
               "-c tools.cmake.cmaketoolchain:system_version=15.1 "
               "-c tools.cmake.cmaketoolchain:system_processor=x86_64 ")

    toolchain = client.load("conan_toolchain.cmake")

    # should set the conf values but system/version are overwritten by the apple block
    assert "CMAKE_SYSTEM_NAME tvOS" in toolchain
    assert "CMAKE_SYSTEM_NAME iOS" not in toolchain
    assert "CMAKE_SYSTEM_VERSION 15.1" in toolchain
    assert "CMAKE_SYSTEM_VERSION 15.0" not in toolchain
    assert "CMAKE_SYSTEM_PROCESSOR x86_64" in toolchain
    assert "CMAKE_SYSTEM_PROCESSOR armv8" not in toolchain


def test_extra_flags_via_conf():
    profile = textwrap.dedent("""
        [settings]
        os=Linux
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        arch=armv8
        build_type=Release

        [conf]
        tools.build:cxxflags=["--flag1", "--flag2"]
        tools.build:cflags+=["--flag3", "--flag4"]
        tools.build:sharedlinkflags=+["--flag5", "--flag6"]
        tools.build:exelinkflags=["--flag7", "--flag8"]
        tools.build:defines=["D1", "D2"]
        """)

    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                "profile": profile})
    client.run("install . --profile:build=profile --profile:host=profile")
    toolchain = client.load("conan_toolchain.cmake")
    assert 'string(APPEND CONAN_CXX_FLAGS " --flag1 --flag2")' in toolchain
    assert 'string(APPEND CONAN_C_FLAGS " --flag3 --flag4")' in toolchain
    assert 'string(APPEND CONAN_SHARED_LINKER_FLAGS " --flag5 --flag6")' in toolchain
    assert 'string(APPEND CONAN_EXE_LINKER_FLAGS " --flag7 --flag8")' in toolchain
    assert 'add_compile_definitions( "D1" "D2")' in toolchain


def test_cmake_presets_binary_dir_available():
    client = TestClient(path_with_spaces=False)
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.cmake import cmake_layout
    class HelloConan(ConanFile):
        generators = "CMakeToolchain"
        settings = "os", "compiler", "build_type", "arch"

        def layout(self):
            cmake_layout(self)

    """)

    client.save({"conanfile.py": conanfile})
    client.run("install .")
    if platform.system() != "Windows":
        build_dir = os.path.join(client.current_folder, "build", "Release")
    else:
        build_dir = os.path.join(client.current_folder, "build")

    presets = load_cmake_presets(os.path.join(client.current_folder, "build", "generators"))
    assert presets["configurePresets"][0]["binaryDir"] == build_dir


def test_cmake_presets_multiconfig():
    client = TestClient()
    profile = textwrap.dedent("""
        [settings]
        os = Windows
        arch = x86_64
        compiler=msvc
        compiler.version=193
        compiler.runtime=static
        compiler.runtime_type=Release
    """)
    client.save({"conanfile.py": GenConanfile(), "profile": profile})
    client.run("create . mylib/1.0@ -s build_type=Release --profile:h=profile")
    client.run("create . mylib/1.0@ -s build_type=Debug --profile:h=profile")

    client.run("install mylib/1.0@ -g CMakeToolchain -s build_type=Release --profile:h=profile")
    presets = json.loads(client.load("CMakePresets.json"))
    assert len(presets["buildPresets"]) == 1
    assert presets["buildPresets"][0]["configuration"] == "Release"

    client.run("install mylib/1.0@ -g CMakeToolchain -s build_type=Debug --profile:h=profile")
    presets = json.loads(client.load("CMakePresets.json"))
    assert len(presets["buildPresets"]) == 2
    assert presets["buildPresets"][0]["configuration"] == "Release"
    assert presets["buildPresets"][1]["configuration"] == "Debug"

    client.run("install mylib/1.0@ -g CMakeToolchain -s build_type=RelWithDebInfo "
               "--profile:h=profile")
    client.run("install mylib/1.0@ -g CMakeToolchain -s build_type=MinSizeRel --profile:h=profile")
    presets = json.loads(client.load("CMakePresets.json"))
    assert len(presets["buildPresets"]) == 4
    assert presets["buildPresets"][0]["configuration"] == "Release"
    assert presets["buildPresets"][1]["configuration"] == "Debug"
    assert presets["buildPresets"][2]["configuration"] == "RelWithDebInfo"
    assert presets["buildPresets"][3]["configuration"] == "MinSizeRel"

    # Repeat one
    client.run("install mylib/1.0@ -g CMakeToolchain -s build_type=Debug --profile:h=profile")
    client.run("install mylib/1.0@ -g CMakeToolchain -s build_type=Debug --profile:h=profile")
    assert len(presets["buildPresets"]) == 4
    assert presets["buildPresets"][0]["configuration"] == "Release"
    assert presets["buildPresets"][1]["configuration"] == "Debug"
    assert presets["buildPresets"][2]["configuration"] == "RelWithDebInfo"
    assert presets["buildPresets"][3]["configuration"] == "MinSizeRel"

    assert len(presets["configurePresets"]) == 1
    assert presets["configurePresets"][0]["name"] == "default"


def test_cmake_presets_singleconfig():
    client = TestClient()
    profile = textwrap.dedent("""
        [settings]
        os = Linux
        arch = x86_64
        compiler=gcc
        compiler.version=8
    """)
    client.save({"conanfile.py": GenConanfile(), "profile": profile})
    client.run("create . mylib/1.0@ -s build_type=Release --profile:h=profile")
    client.run("create . mylib/1.0@ -s build_type=Debug --profile:h=profile")

    client.run("install mylib/1.0@ -g CMakeToolchain -s build_type=Release --profile:h=profile")
    presets = json.loads(client.load("CMakePresets.json"))
    assert len(presets["configurePresets"]) == 1
    assert presets["configurePresets"][0]["name"] == "release"

    assert len(presets["buildPresets"]) == 1
    assert presets["buildPresets"][0]["configurePreset"] == "release"

    # Now two configurePreset, but named correctly
    client.run("install mylib/1.0@ -g CMakeToolchain -s build_type=Debug --profile:h=profile")
    presets = json.loads(client.load("CMakePresets.json"))
    assert len(presets["configurePresets"]) == 2
    assert presets["configurePresets"][1]["name"] == "debug"

    assert len(presets["buildPresets"]) == 2
    assert presets["buildPresets"][1]["configurePreset"] == "debug"

    # Repeat configuration, it shouldn't add a new one
    client.run("install mylib/1.0@ -g CMakeToolchain -s build_type=Debug --profile:h=profile")
    presets = json.loads(client.load("CMakePresets.json"))
    assert len(presets["configurePresets"]) == 2


def test_toolchain_cache_variables():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMakeToolchain, CMake

        class Conan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"

            def generate(self):
                toolchain = CMakeToolchain(self)
                toolchain.cache_variables["foo"] = True
                toolchain.cache_variables["foo2"] = False
                toolchain.cache_variables["var"] = "23"
                toolchain.cache_variables["CMAKE_SH"] = "THIS VALUE HAS PRIORITY"
                toolchain.cache_variables["CMAKE_POLICY_DEFAULT_CMP0091"] = "THIS VALUE HAS PRIORITY"
                toolchain.cache_variables["CMAKE_MAKE_PROGRAM"] = "THIS VALUE HAS NO PRIORITY"
                toolchain.generate()
        """)
    client.save({"conanfile.py": conanfile})
    with mock.patch("platform.system", mock.MagicMock(return_value="Windows")):
        client.run("install . mylib/1.0@ -c tools.cmake.cmaketoolchain:generator='MinGW Makefiles' "
                   "-c tools.gnu:make_program='MyMake' -c tools.build:skip_test=True")
    presets = json.loads(client.load("CMakePresets.json"))
    cache_variables = presets["configurePresets"][0]["cacheVariables"]
    assert cache_variables["foo"] == 'ON'
    assert cache_variables["foo2"] == 'OFF'
    assert cache_variables["var"] == '23'
    assert cache_variables["CMAKE_SH"] == "THIS VALUE HAS PRIORITY"
    assert cache_variables["CMAKE_POLICY_DEFAULT_CMP0091"] == "THIS VALUE HAS PRIORITY"
    assert cache_variables["CMAKE_MAKE_PROGRAM"] == "MyMake"
    assert cache_variables["BUILD_TESTING"] == 'OFF'


def test_android_c_library():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Conan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeToolchain"

            def configure(self):
                del self.settings.compiler.libcxx

        """)
    client.save({"conanfile.py": conanfile})
    # Settings
    settings = "-s arch=x86_64 -s os=Android -s os.api_level=23 -c tools.android:ndk_path=/foo"
    # Checking the Android variables created
    # Issue: https://github.com/conan-io/conan/issues/11798
    client.run("install . " + settings)
    conan_toolchain = client.load(os.path.join(client.current_folder, "conan_toolchain.cmake"))
    assert "set(ANDROID_PLATFORM android-23)" in conan_toolchain
    assert "set(ANDROID_ABI x86_64)" in conan_toolchain
    assert "include(/foo/build/cmake/android.toolchain.cmake)" in conan_toolchain
    client.run("create . foo/1.0@ " + settings)


def test_user_presets_version2():
    client = TestClient()
    conanfile = textwrap.dedent("""
                from conan import ConanFile
                from conan.tools.cmake import cmake_layout

                class Conan(ConanFile):
                    name = "foo"
                    version = "1.0"
                    settings = "os", "arch", "compiler", "build_type"
                    generators = "CMakeToolchain"

                    def layout(self):
                        cmake_layout(self)

            """)
    client.save({"conanfile.py": conanfile, "CMakeLists.txt": "foo"})
    configs = ["-c tools.cmake.cmaketoolchain.presets:max_schema_version=2 ",
               "-c tools.cmake.cmake_layout:build_folder_vars='[\"settings.compiler.cppstd\"]'"]
    client.run("install . {} -s compiler.cppstd=14".format(" ".join(configs)))
    client.run("install . {} -s compiler.cppstd=17".format(" ".join(configs)))

    presets = json.loads(client.load("CMakeUserPresets.json"))
    assert len(presets["configurePresets"]) == 2
    assert presets["version"] == 2
    assert "build/14/generators/conan_toolchain.cmake" \
           in presets["configurePresets"][0]["cacheVariables"]["CMAKE_TOOLCHAIN_FILE"].replace("\\",
                                                                                               "/")
    assert "build/17/generators/conan_toolchain.cmake" \
           in presets["configurePresets"][1]["cacheVariables"]["CMAKE_TOOLCHAIN_FILE"].replace("\\",
                                                                                               "/")


def test_user_presets_version2_no_overwrite_user():

    client = TestClient()
    conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import cmake_layout

            class Conan(ConanFile):
                name = "foo"
                version = "1.0"
                settings = "os", "arch", "compiler", "build_type"
                generators = "CMakeToolchain"

                def layout(self):
                    cmake_layout(self)

            """)
    client.save({"conanfile.py": conanfile, "CMakeLists.txt": "foo",
                 "CMakeUserPresets.json": '{"from_user": 1}'})
    configs = ["-c tools.cmake.cmaketoolchain.presets:max_schema_version=2 ",
               "-c tools.cmake.cmake_layout:build_folder_vars='[\"settings.compiler.cppstd\"]'"]
    client.run("install . {} -s compiler.cppstd=14".format(" ".join(configs)))

    presets = json.loads(client.load("CMakeUserPresets.json"))
    assert presets == {"from_user": 1}


@pytest.mark.skipif(platform.system() != "Windows", reason="Only Windows")
def test_presets_paths_correct():
    client = TestClient()
    conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import cmake_layout

            class Conan(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                generators = "CMakeToolchain"

                def layout(self):
                    cmake_layout(self)
            """)
    client.save({"conanfile.py": conanfile, "CMakeLists.txt": "foo"})
    configs = ["-c tools.cmake.cmaketoolchain.presets:max_schema_version=2 ",
               "-c tools.cmake.cmake_layout:build_folder_vars='[\"settings.compiler.cppstd\"]'"]
    client.run("install . {} -s compiler.cppstd=14".format(" ".join(configs)))
    client.run("install . {} -s compiler.cppstd=17".format(" ".join(configs)))

    presets = json.loads(client.load("CMakeUserPresets.json"))
    assert len(presets["configurePresets"]) == 2
    assert presets["version"] == 2
    assert "build/14/generators/conan_toolchain.cmake" \
           in presets["configurePresets"][0]["cacheVariables"]["CMAKE_TOOLCHAIN_FILE"].replace("\\",
                                                                                               "/")
    assert "build/17/generators/conan_toolchain.cmake" \
           in presets["configurePresets"][1]["cacheVariables"]["CMAKE_TOOLCHAIN_FILE"].replace("\\",
                                                                                               "/")


@pytest.mark.skipif(platform.system() != "Windows", reason="Only Windows")
def test_presets_paths_normalization():
    # https://github.com/conan-io/conan/issues/11795
    client = TestClient()
    conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import cmake_layout

            class Conan(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                generators = "CMakeToolchain"

                def layout(self):
                    cmake_layout(self)
            """)
    client.save({"conanfile.py": conanfile, "CMakeLists.txt": "foo"})
    client.run("install .")

    presets = json.loads(client.load("CMakeUserPresets.json"))

    assert "/" not in presets["include"]


def test_presets_updated():
    """If a preset file is generated more than once, the values are always added and, in case the
    configurePreset or buildPreset already exist, the new preset is updated """
    client = TestClient()
    conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import cmake_layout

            class Conan(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                generators = "CMakeToolchain"

                def layout(self):
                    cmake_layout(self)
            """)
    client.save({"conanfile.py": conanfile, "CMakeLists.txt": "foo"})
    configs = ["-c tools.cmake.cmaketoolchain.presets:max_schema_version=2 ",
               "-c tools.cmake.cmake_layout:build_folder_vars='[\"settings.compiler.cppstd\"]'"]
    client.run("install . {} -s compiler.cppstd=14".format(" ".join(configs)))
    client.run("install . {} -s compiler.cppstd=17".format(" ".join(configs)))

    presets = json.loads(client.load("CMakeUserPresets.json"))
    assert len(presets["configurePresets"]) == 2
    assert "FOO" not in presets["configurePresets"][0]["cacheVariables"]

    # Now introduce a cache_variable FOO to see if we get it in the CMakeUserPresets.json (that
    # at the same time, it will come from the build/xxxx/CMakePreset.json that is also updated)
    conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import cmake_layout, CMakeToolchain

            class Conan(ConanFile):
                settings = "os", "arch", "compiler", "build_type"

                def generate(self):
                    tc = CMakeToolchain(self)
                    tc.cache_variables["FOO"] = "var"
                    tc.generate()

                def layout(self):
                    cmake_layout(self)
            """)
    client.save({"conanfile.py": conanfile})
    client.run("install . {} -s compiler.cppstd=14".format(" ".join(configs)))
    presets = json.loads(client.load("CMakeUserPresets.json"))
    assert len(presets["configurePresets"]) == 2
    assert "FOO" in presets["configurePresets"][0]["cacheVariables"]


@pytest.mark.parametrize("arch, arch_toolset", [("x86", "x86_64"), ("x86_64", "x86_64")])
def test_presets_ninja_msvc(arch, arch_toolset):
    client = TestClient()
    conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import cmake_layout

            class Conan(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                generators = "CMakeToolchain"

                def layout(self):
                    cmake_layout(self)
            """)
    client.save({"conanfile.py": conanfile, "CMakeLists.txt": "foo"})
    configs = ["-c tools.cmake.cmaketoolchain:toolset_arch={}".format(arch_toolset),
               "-c tools.cmake.cmake_layout:build_folder_vars='[\"settings.compiler.cppstd\"]'",
               "-c tools.cmake.cmaketoolchain:generator=Ninja"]
    msvc = " -s compiler=msvc -s compiler.version=191 -s compiler.runtime=static " \
           "-s compiler.runtime_type=Release"
    client.run("install . {} -s compiler.cppstd=14 {} -s arch={}".format(" ".join(configs), msvc, arch))

    presets = json.loads(client.load("build/14/generators/CMakePresets.json"))

    toolset_value = {"x86_64": "host=x86_64", "x86": "x86"}.get(arch_toolset)
    arch_value = {"x86_64": "x64", "x86": "x86"}.get(arch)

    assert presets["configurePresets"][0]["architecture"]["value"] == arch_value
    assert presets["configurePresets"][0]["architecture"]["strategy"] == "external"
    assert presets["configurePresets"][0]["toolset"]["value"] == toolset_value
    assert presets["configurePresets"][0]["toolset"]["strategy"] == "external"

    # Only for Ninja, no ninja, no values
    rmdir(os.path.join(client.current_folder, "build"))
    configs = ["-c tools.cmake.cmaketoolchain:toolset_arch={}".format(arch_toolset),
               "-c tools.cmake.cmake_layout:build_folder_vars='[\"settings.compiler.cppstd\"]'"]
    client.run(
        "install . {} -s compiler.cppstd=14 {} -s arch={}".format(" ".join(configs), msvc, arch))

    presets = json.loads(client.load("build/14/generators/CMakePresets.json"))
    assert "architecture" not in presets["configurePresets"][0]
    assert "toolset" not in presets["configurePresets"][0]

    # No toolset defined in conf, no value
    rmdir(os.path.join(client.current_folder, "build"))
    configs = ["-c tools.cmake.cmake_layout:build_folder_vars='[\"settings.compiler.cppstd\"]'",
               "-c tools.cmake.cmaketoolchain:generator=Ninja"]

    client.run(
        "install . {} -s compiler.cppstd=14 {} -s arch={}".format(" ".join(configs), msvc, arch))
    presets = json.loads(client.load("build/14/generators/CMakePresets.json"))
    assert "architecture" in presets["configurePresets"][0]
    assert "toolset" not in presets["configurePresets"][0]
