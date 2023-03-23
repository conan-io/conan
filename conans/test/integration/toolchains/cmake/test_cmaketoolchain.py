import json
import os
import platform
import textwrap

import pytest
from mock import mock

from conan.tools.cmake.presets import load_cmake_presets
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import rmdir, load


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
        from conan import ConanFile

        class Conan(ConanFile):

            def package_info(self):
                self.cpp_info.builddirs = ["/path/to/builddir"]
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=dep --version=1.0")

    conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMakeToolchain

            class Conan(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                requires = "dep/1.0@"

                def generate(self):
                    cmake = CMakeToolchain(self)
                    cmake.generate()
            """)

    client.save({"conanfile.py": conanfile})
    client.run("install . ")
    with open(os.path.join(client.current_folder, "conan_toolchain.cmake")) as f:
        contents = f.read()
        assert "/path/to/builddir" in contents

    conanfile = textwrap.dedent("""
       import os
       from conan import ConanFile
       from conan.tools.cmake import CMakeToolchain

       class Conan(ConanFile):
           name = "mydep"
           version = "1.0"
           settings = "os", "arch", "compiler", "build_type"

           def build_requirements(self):
               self.test_requires("dep/1.0")

           def generate(self):
               cmake = CMakeToolchain(self)
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

    presets = load_cmake_presets(os.path.join(build_dir, "generators"))
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
    client.save({"conanfile.py": GenConanfile("mylib", "1.0"), "profile": profile})
    client.run("create . -s build_type=Release --profile:h=profile")
    client.run("create . -s build_type=Debug --profile:h=profile")

    client.run("install --requires=mylib/1.0@ -g CMakeToolchain "
               "-s build_type=Release --profile:h=profile")
    presets = json.loads(client.load("CMakePresets.json"))
    assert len(presets["configurePresets"]) == 1
    assert len(presets["buildPresets"]) == 1
    assert presets["buildPresets"][0]["configuration"] == "Release"
    assert len(presets["testPresets"]) == 1
    assert presets["testPresets"][0]["configuration"] == "Release"

    client.run("install --requires=mylib/1.0@ -g CMakeToolchain "
               "-s build_type=Debug --profile:h=profile")
    presets = json.loads(client.load("CMakePresets.json"))
    assert len(presets["configurePresets"]) == 1
    assert len(presets["buildPresets"]) == 2
    assert presets["buildPresets"][0]["configuration"] == "Release"
    assert presets["buildPresets"][1]["configuration"] == "Debug"
    assert len(presets["testPresets"]) == 2
    assert presets["testPresets"][0]["configuration"] == "Release"
    assert presets["testPresets"][1]["configuration"] == "Debug"

    client.run("install --requires=mylib/1.0@ -g CMakeToolchain "
               "-s build_type=RelWithDebInfo --profile:h=profile")
    client.run("install --requires=mylib/1.0@ -g CMakeToolchain "
               "-s build_type=MinSizeRel --profile:h=profile")

    presets = json.loads(client.load("CMakePresets.json"))
    assert len(presets["configurePresets"]) == 1
    assert len(presets["buildPresets"]) == 4
    assert presets["buildPresets"][0]["configuration"] == "Release"
    assert presets["buildPresets"][1]["configuration"] == "Debug"
    assert presets["buildPresets"][2]["configuration"] == "RelWithDebInfo"
    assert presets["buildPresets"][3]["configuration"] == "MinSizeRel"
    assert len(presets["testPresets"]) == 4
    assert presets["testPresets"][0]["configuration"] == "Release"
    assert presets["testPresets"][1]["configuration"] == "Debug"
    assert presets["testPresets"][2]["configuration"] == "RelWithDebInfo"
    assert presets["testPresets"][3]["configuration"] == "MinSizeRel"

    # Repeat one
    client.run("install --requires=mylib/1.0@ -g CMakeToolchain "
               "-s build_type=Debug --profile:h=profile")
    client.run("install --requires=mylib/1.0@ -g CMakeToolchain "
               "-s build_type=Debug --profile:h=profile")
    presets = json.loads(client.load("CMakePresets.json"))
    assert len(presets["configurePresets"]) == 1
    assert len(presets["buildPresets"]) == 4
    assert presets["buildPresets"][0]["configuration"] == "Release"
    assert presets["buildPresets"][1]["configuration"] == "Debug"
    assert presets["buildPresets"][2]["configuration"] == "RelWithDebInfo"
    assert presets["buildPresets"][3]["configuration"] == "MinSizeRel"

    assert len(presets["testPresets"]) == 4
    assert presets["testPresets"][0]["configuration"] == "Release"
    assert presets["testPresets"][1]["configuration"] == "Debug"
    assert presets["testPresets"][2]["configuration"] == "RelWithDebInfo"
    assert presets["testPresets"][3]["configuration"] == "MinSizeRel"

    assert len(presets["configurePresets"]) == 1
    assert presets["configurePresets"][0]["name"] == "conan-default"


def test_cmake_presets_singleconfig():
    """ without defining a layout, single config always overwrites
    the existing CMakePresets.json
    """
    client = TestClient()
    profile = textwrap.dedent("""
        [settings]
        os = Linux
        arch = x86_64
        compiler=gcc
        compiler.version=8
    """)
    client.save({"conanfile.py": GenConanfile("mylib", "1.0"), "profile": profile})
    client.run("create . -s build_type=Release --profile:h=profile")
    client.run("create . -s build_type=Debug --profile:h=profile")

    client.run("install --requires=mylib/1.0@ "
               "-g CMakeToolchain -s build_type=Release --profile:h=profile")
    presets = json.loads(client.load("CMakePresets.json"))
    assert len(presets["configurePresets"]) == 1
    assert presets["configurePresets"][0]["name"] == "conan-release"

    assert len(presets["buildPresets"]) == 1
    assert presets["buildPresets"][0]["configurePreset"] == "conan-release"

    assert len(presets["testPresets"]) == 1
    assert presets["testPresets"][0]["configurePreset"] == "conan-release"

    # This overwrites the existing profile, as there is no layout
    client.run("install --requires=mylib/1.0@ "
               "-g CMakeToolchain -s build_type=Debug --profile:h=profile")

    presets = json.loads(client.load("CMakePresets.json"))
    assert len(presets["configurePresets"]) == 1
    assert presets["configurePresets"][0]["name"] == "conan-debug"

    assert len(presets["buildPresets"]) == 1
    assert presets["buildPresets"][0]["configurePreset"] == "conan-debug"

    assert len(presets["testPresets"]) == 1
    assert presets["testPresets"][0]["configurePreset"] == "conan-debug"

    # Repeat configuration, it shouldn't add a new one
    client.run("install --requires=mylib/1.0@ "
               "-g CMakeToolchain -s build_type=Debug --profile:h=profile")
    presets = json.loads(client.load("CMakePresets.json"))
    assert len(presets["configurePresets"]) == 1


def test_toolchain_cache_variables():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeToolchain

        class Conan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            options = {"enable_foobar": [True, False], "qux": ["ANY"], "number": [1,2]}
            default_options = {"enable_foobar": True, "qux": "baz", "number": 1}

            def generate(self):
                toolchain = CMakeToolchain(self)
                toolchain.cache_variables["foo"] = True
                toolchain.cache_variables["foo2"] = False
                toolchain.cache_variables["var"] = "23"
                toolchain.cache_variables["ENABLE_FOOBAR"] = self.options.enable_foobar
                toolchain.cache_variables["QUX"] = self.options.qux
                toolchain.cache_variables["NUMBER"] = self.options.number
                toolchain.cache_variables["CMAKE_SH"] = "THIS VALUE HAS PRIORITY"
                toolchain.cache_variables["CMAKE_POLICY_DEFAULT_CMP0091"] = "THIS VALUE HAS PRIORITY"
                toolchain.cache_variables["CMAKE_MAKE_PROGRAM"] = "THIS VALUE HAS NO PRIORITY"
                toolchain.generate()
        """)
    client.save({"conanfile.py": conanfile})
    with mock.patch("platform.system", mock.MagicMock(return_value="Windows")):
        client.run("install . --name=mylib --version=1.0 "
                   "-c tools.cmake.cmaketoolchain:generator='MinGW Makefiles' "
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
    assert cache_variables["ENABLE_FOOBAR"] == 'ON'
    assert cache_variables["QUX"] == 'baz'
    assert cache_variables["NUMBER"] == 1

    def _format_val(val):
        return f'"{val}"' if type(val) == str and " " in val else f"{val}"

    for var, value in cache_variables.items():
        assert f"-D{var}={_format_val(value)}" in client.out
    assert "-DCMAKE_TOOLCHAIN_FILE=" in client.out
    assert f"-G {_format_val('MinGW Makefiles')}" in client.out


def test_android_c_library():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Conan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeToolchain"

            def configure(self):
                if self.settings.compiler != "msvc":
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
    client.run("create . --name=foo --version=1.0 " + settings)


@pytest.mark.parametrize("cmake_legacy_toolchain", [True, False, None])
def test_android_legacy_toolchain_flag(cmake_legacy_toolchain):
    client = TestClient()
    conanfile = GenConanfile().with_settings("os", "arch")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile})
    settings = "-s arch=x86_64 -s os=Android -s os.api_level=23 -c tools.android:ndk_path=/foo"
    if cmake_legacy_toolchain is not None:
        settings += f" -c tools.android:cmake_legacy_toolchain={cmake_legacy_toolchain}"
        expected = "ON" if cmake_legacy_toolchain else "OFF"
    client.run("install . " + settings)
    conan_toolchain = client.load(os.path.join(client.current_folder, "conan_toolchain.cmake"))
    if cmake_legacy_toolchain is not None:
        assert f"set(ANDROID_USE_LEGACY_TOOLCHAIN_FILE {expected})" in conan_toolchain
    else:
        assert "ANDROID_USE_LEGACY_TOOLCHAIN_FILE" not in conan_toolchain


@pytest.mark.parametrize("cmake_legacy_toolchain", [True, False, None])
def test_android_legacy_toolchain_with_compileflags(cmake_legacy_toolchain):
    # https://github.com/conan-io/conan/issues/13374
    client = TestClient()
    conanfile = GenConanfile().with_settings("os", "arch")\
        .with_generator("CMakeToolchain")
    profile = textwrap.dedent("""
    [settings]
    os=Android
    os.api_level=23
    arch=armv8

    [conf]
    tools.android:ndk_path=/foo
    tools.build:cflags=["-foobar"]
    tools.build:cxxflags=["-barfoo"]
    """)
    if cmake_legacy_toolchain is not None:
        profile += f"\ntools.android:cmake_legacy_toolchain={cmake_legacy_toolchain}"

    client.save({"conanfile.py": conanfile, "profile_host": profile})
    client.run("install . -pr profile_host")
    warning_text = "Consider setting tools.android:cmake_legacy_toolchain to False"
    if cmake_legacy_toolchain is not False:
        assert warning_text in client.out
    else:
        assert warning_text not in client.out


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

    presets = json.loads(client.load("build/14/Release/generators/CMakePresets.json"))

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
    presets = json.loads(client.load("build/14/Release/generators/CMakePresets.json"))
    assert "architecture" in presets["configurePresets"][0]
    assert "toolset" not in presets["configurePresets"][0]


def test_pkg_config_block():
    os_ = platform.system()
    os_ = "Macos" if os_ == "Darwin" else os_
    profile = textwrap.dedent("""
        [settings]
        os=%s
        arch=x86_64

        [conf]
        tools.gnu:pkg_config=/usr/local/bin/pkg-config
        """ % os_)

    client = TestClient(path_with_spaces=False)
    conanfile = GenConanfile().with_settings("os", "arch")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                "profile": profile})
    client.run("install . -pr:b profile -pr:h profile")
    toolchain = client.load("conan_toolchain.cmake")
    assert 'set(PKG_CONFIG_EXECUTABLE /usr/local/bin/pkg-config CACHE FILEPATH ' in toolchain
    pathsep = ":" if os_ != "Windows" else ";"
    pkg_config_path_set = 'set(ENV{PKG_CONFIG_PATH} "%s$ENV{PKG_CONFIG_PATH}")' % \
                          (client.current_folder.replace("\\", "/") + pathsep)
    assert pkg_config_path_set in toolchain


@pytest.mark.parametrize("path", ["subproject", False])
def test_user_presets_custom_location(path):
    client = TestClient()
    conanfile = textwrap.dedent("""
                import os
                from conan import ConanFile
                from conan.tools.cmake import cmake_layout, CMakeToolchain

                class Conan(ConanFile):
                    settings = "os", "arch", "compiler", "build_type"

                    def generate(self):
                        t = CMakeToolchain(self)
                        t.user_presets_path = {}
                        t.generate()

                    def layout(self):
                        cmake_layout(self)
                """.format('"{}"'.format(path) if isinstance(path, str) else path))
    client.save({"CMakeLists.txt": "",
                 "subproject/CMakeLists.txt": "",
                 "subproject2/foo.txt": "",
                 "conanfile.py": conanfile})

    # We want to generate it to build the subproject
    client.run("install . ")

    if path is not False:
        assert not os.path.exists(os.path.join(client.current_folder, "CMakeUserPresets.json"))
        assert os.path.exists(os.path.join(client.current_folder, "subproject", "CMakeUserPresets.json"))
    else:
        assert not os.path.exists(os.path.join(client.current_folder, "CMakeUserPresets.json"))
        assert not os.path.exists(os.path.join(client.current_folder, "False", "CMakeUserPresets.json"))


def test_set_cmake_lang_compilers_and_launchers():
    profile = textwrap.dedent(r"""
    [settings]
    os=Windows
    arch=x86_64
    compiler=clang
    compiler.version=15
    compiler.libcxx=libstdc++11
    [conf]
    tools.build:compiler_executables={"c": "/my/local/gcc", "cpp": "g++", "rc": "C:\\local\\rc.exe"}
    """)
    client = TestClient(path_with_spaces=False)
    conanfile = GenConanfile().with_settings("os", "arch", "compiler")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                "profile": profile})
    client.run("install . -pr:b profile -pr:h profile")
    toolchain = client.load("conan_toolchain.cmake")
    assert 'set(CMAKE_C_COMPILER clang)' not in toolchain
    assert 'set(CMAKE_CXX_COMPILER clang++)' not in toolchain
    assert 'set(CMAKE_C_COMPILER "/my/local/gcc")' in toolchain
    assert 'set(CMAKE_CXX_COMPILER "g++")' in toolchain
    assert 'set(CMAKE_RC_COMPILER "C:/local/rc.exe")' in toolchain


def test_cmake_layout_toolchain_folder():
    """ in single-config generators, the toolchain is a different file per configuration
    https://github.com/conan-io/conan/issues/12827
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class Conan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeToolchain"

            def layout(self):
                cmake_layout(self)
            """)
    c.save({"conanfile.py": conanfile})
    c.run("install . -s os=Linux -s compiler=gcc -s compiler.version=7 -s build_type=Release "
          "-s compiler.libcxx=libstdc++11")
    assert os.path.exists(os.path.join(c.current_folder,
                                       "build/Release/generators/conan_toolchain.cmake"))
    c.run("install . -s os=Linux -s compiler=gcc -s compiler.version=7 -s build_type=Debug "
          "-s compiler.libcxx=libstdc++11")
    assert os.path.exists(os.path.join(c.current_folder,
                                       "build/Debug/generators/conan_toolchain.cmake"))
    c.run("install . -s os=Linux -s compiler=gcc -s compiler.version=7 -s build_type=Debug "
          "-s compiler.libcxx=libstdc++11 -s arch=x86 "
          "-c tools.cmake.cmake_layout:build_folder_vars='[\"settings.arch\", \"settings.build_type\"]'")
    assert os.path.exists(os.path.join(c.current_folder,
                                       "build/x86-debug/generators/conan_toolchain.cmake"))
    c.run("install . -s os=Linux -s compiler=gcc -s compiler.version=7 -s build_type=Debug "
          "-s compiler.libcxx=libstdc++11 -s arch=x86 "
          "-c tools.cmake.cmake_layout:build_folder_vars='[\"settings.os\"]'")
    assert os.path.exists(os.path.join(c.current_folder,
                                       "build/linux/Debug/generators/conan_toolchain.cmake"))


def test_build_folder_vars_editables():
    """ when packages are in editable, they must also follow the build_folder_vars
    https://github.com/conan-io/conan/issues/13485
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class Conan(ConanFile):
            name = "dep"
            version = "0.1"
            settings = "os", "build_type"
            generators = "CMakeToolchain"

            def layout(self):
                cmake_layout(self)
        """)
    c.save({"dep/conanfile.py": conanfile,
            "app/conanfile.py": GenConanfile().with_requires("dep/0.1")})
    c.run("editable add dep")
    conf = "tools.cmake.cmake_layout:build_folder_vars='[\"settings.os\", \"settings.build_type\"]'"
    settings = " -s os=FreeBSD -s arch=armv8 -s build_type=Debug"
    c.run("install app -c={} {}".format(conf, settings))
    assert os.path.exists(os.path.join(c.current_folder, "dep", "build", "freebsd-debug"))


def test_set_linker_scripts():
    profile = textwrap.dedent(r"""
    [settings]
    os=Windows
    arch=x86_64
    compiler=clang
    compiler.version=15
    compiler.libcxx=libstdc++11
    [conf]
    tools.build:linker_scripts=["/usr/local/src/flash.ld", "C:\\local\\extra_data.ld"]
    """)
    client = TestClient(path_with_spaces=False)
    conanfile = GenConanfile().with_settings("os", "arch", "compiler")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                "profile": profile})
    client.run("install . -pr:b profile -pr:h profile")
    toolchain = client.load("conan_toolchain.cmake")
    assert 'string(APPEND CONAN_EXE_LINKER_FLAGS -T"/usr/local/src/flash.ld" -T"C:/local/extra_data.ld")' in toolchain


def test_test_package_layout():
    """
    test that the ``test_package`` folder also follows the cmake_layout and the
    build_folder_vars
    """
    client = TestClient()
    test_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class Conan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeToolchain"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def layout(self):
                cmake_layout(self)

            def test(self):
                pass
    """)
    client.save({"conanfile.py": GenConanfile("pkg", "0.1"),
                 "test_package/conanfile.py": test_conanfile})
    config = "-c tools.cmake.cmake_layout:build_folder_vars='[\"settings.compiler.cppstd\"]'"
    client.run(f"create . {config} -s compiler.cppstd=14")
    build_folder = client.created_test_build_folder("pkg/0.1")
    assert os.path.exists(os.path.join(client.current_folder, "test_package", build_folder))
    client.run(f"create . {config} -s compiler.cppstd=17")
    build_folder2 = client.created_test_build_folder("pkg/0.1")
    assert os.path.exists(os.path.join(client.current_folder, "test_package", build_folder2))
    assert build_folder != build_folder2


def test_presets_not_found_error_msg():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class Conan(ConanFile):
            settings = "build_type"

            def build(self):
                CMake(self).configure()
    """)
    client.save({"conanfile.py": conanfile})
    client.run("build .", assert_error=True)
    assert "CMakePresets.json was not found" in client.out
    assert "Check that you are using CMakeToolchain as generator " \
           "to ensure its correct initialization." in client.out


def test_recipe_build_folders_vars():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class Conan(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os", "arch", "build_type"
            options = {"shared": [True, False]}
            generators = "CMakeToolchain"

            def layout(self):
                self.folders.build_folder_vars = ["settings.os", "options.shared"]
                cmake_layout(self)
        """)
    client.save({"conanfile.py": conanfile})
    client.run("install . -s os=Windows -s arch=armv8 -s build_type=Debug -o shared=True")
    presets = client.load("build/windows-shared/Debug/generators/CMakePresets.json")
    assert "conan-windows-shared-debug" in presets
    client.run("install . -s os=Linux -s arch=x86 -s build_type=Release -o shared=False")
    presets = client.load("build/linux-static/Release/generators/CMakePresets.json")
    assert "linux-static-release" in presets

    # CLI override has priority
    client.run("install . -s os=Linux -s arch=x86 -s build_type=Release -o shared=False "
               "-c tools.cmake.cmake_layout:build_folder_vars='[\"settings.os\"]'")
    presets = client.load("build/linux/Release/generators/CMakePresets.json")
    assert "conan-linux-release" in presets

    # Now we do the build in the cache, the recipe folders are still used
    client.run("create . -s os=Windows -s arch=armv8 -s build_type=Debug -o shared=True")
    ref = client.created_package_reference("pkg/0.1")
    layout = client.get_latest_pkg_layout(ref)
    build_folder = layout.build()
    presets = load(os.path.join(build_folder,
                                "build/windows-shared/Debug/generators/CMakePresets.json"))
    assert "conan-windows-shared-debug" in presets

    # If we change the conf ``build_folder_vars``, it doesn't affect the cache build
    client.run("create . -s os=Windows -s arch=armv8 -s build_type=Debug -o shared=True "
               "-c tools.cmake.cmake_layout:build_folder_vars='[\"settings.os\"]'")
    ref = client.created_package_reference("pkg/0.1")
    layout = client.get_latest_pkg_layout(ref)
    build_folder = layout.build()
    presets = load(os.path.join(build_folder,
                                "build/windows-shared/Debug/generators/CMakePresets.json"))
    assert "conan-windows-shared-debug" in presets
