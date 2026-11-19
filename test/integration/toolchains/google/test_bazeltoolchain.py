import os
import textwrap
from unittest import mock

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def conanfile():
    return textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.google import BazelToolchain, bazel_layout
        class ExampleConanIntegration(ConanFile):
            settings = "os", "arch", "build_type", "compiler"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}
            generators = 'BazelToolchain'
            def layout(self):
                bazel_layout(self)
    """)


_macos_x86_64 = textwrap.dedent("""
    [settings]
    arch=x86_64
    build_type=Release
    compiler=apple-clang
    compiler.cppstd=gnu17
    compiler.libcxx=libc++
    compiler.version=13.0
    os=Macos
    """)

_linux_x86_64 = textwrap.dedent("""
    [settings]
    arch=x86_64
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    [conf]
    tools.build:compiler_executables={"c": "/opt/gcc/bin/gcc", "cpp": "/opt/gcc/bin/g++"}
    """)


def _build_file(client, folder="conan"):
    return client.load(os.path.join(folder, "conan_toolchain", "BUILD.bazel"))


def test_default_bazel_toolchain(conanfile):
    """
    Native build: platforms + cc_toolchain are generated, the toolchain is registered by the
    MODULE.bazel snippet and no bazelrc file is needed
    """
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": _linux_x86_64})
    c.run("install . -pr:a profile")
    assert ("BazelToolchain generated: //conan:conan_toolchain.MODULE.bazel and conan_bzl.rc "
            "(--config=conan-config)") in c.out
    # The bazelrc is always generated: Bazel strips the debug symbols in its default "fastbuild"
    bazelrc = c.load("conan/conan_bzl.rc")
    assert "build:conan-config --strip=never" in bazelrc
    assert "--platforms" not in bazelrc
    assert "--compilation_mode" not in bazelrc
    assert os.path.exists(os.path.join(c.current_folder, "conan", "BUILD.bazel"))
    # The official rules_cc toolchain config rule is used, no custom Starlark rules
    assert os.listdir(os.path.join(c.current_folder, "conan", "conan_toolchain")) == \
        ["BUILD.bazel"]
    module = c.load("conan/conan_toolchain.MODULE.bazel")
    assert 'include("//conan:conan_toolchain.MODULE.bazel")' in module
    assert 'register_toolchains("//conan/conan_toolchain:cc_toolchain")' in module

    build = _build_file(c)
    host_platform = textwrap.dedent("""\
        platform(
            name = "host_platform",
            constraint_values = [
                "@platforms//os:linux",
                "@platforms//cpu:x86_64",
            ],
        )""")
    assert host_platform in build
    assert 'toolchain_identifier = "conan_linux_x86_64_gcc_11"' in build
    assert ('load("@rules_cc//cc/private/toolchain:unix_cc_toolchain_config.bzl", '
            '"cc_toolchain_config")') in build
    assert "cc_args" not in build  # No extra rule-based features needed
    assert "extra_enabled_features" not in build
    assert 'compiler = "gcc"' in build
    assert 'cpu = "x86_64"' in build
    assert 'target_libc = "unknown"' in build
    assert '"gcc": "/opt/gcc/bin/gcc"' in build
    assert '"cpp": "/opt/gcc/bin/cpp"' in build
    assert '"/opt/gcc",' in build  # compiler installation, cxx_builtin_include_directories
    compile_flags = ('    compile_flags = [\n'
                     '        "-m64",\n'
                     '        "-O3",\n'
                     '        "-DNDEBUG",\n'
                     '        "-fPIC",\n'
                     '    ],')
    assert compile_flags in build
    assert '"-std=gnu++17",' in build
    assert '"-lstdc++",' in build
    assert 'toolchain_type = "@bazel_tools//tools/cpp:toolchain_type"' in build


def test_bazel_toolchain_and_flags(conanfile):
    profile = textwrap.dedent("""
    [options]
    shared=True
    [conf]
    tools.build:cxxflags=["--flag1", "--flag2"]
    tools.build:cflags+=["--flag3", "--flag4"]
    tools.build:sharedlinkflags+=["--flag5"]
    tools.build:exelinkflags+=["--flag6"]
    tools.build:linker_scripts+=["myscript.sh"]
    tools.build:defines+=["MYDEFINE=1"]
    tools.build:sysroot=/my/sysroot
    """)
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile_base": _macos_x86_64,
            "profile": "include(profile_base)\n" + profile})
    c.run("install . -pr:h profile -pr:b profile_base")
    build = _build_file(c)
    assert '"-fPIC"' not in build  # shared library, Bazel manages PIC
    assert '"-DMYDEFINE=1",' in build
    assert ('    conly_flags = [\n'
            '        "--flag3",\n'
            '        "--flag4",\n'
            '    ],') in build
    assert ('    cxx_flags = [\n'
            '        "-std=gnu++17",\n'
            '        "-stdlib=libc++",\n'
            '        "--flag1",\n'
            '        "--flag2",\n'
            '    ],') in build
    assert '"-Tmyscript.sh",' in build
    # Exe and shared link flags are injected as rules_cc rule-based features
    assert textwrap.dedent("""\
        cc_args(
            name = "conan_exe_link_flags_args",
            actions = [
                "@rules_cc//cc/toolchains/actions:cpp_link_executable",
            ],
            args = [
                "--flag6",
            ],
        )""") in build
    assert textwrap.dedent("""\
        cc_args(
            name = "conan_shared_link_flags_args",
            actions = [
                "@rules_cc//cc/toolchains/actions:dynamic_library_link_actions",
            ],
            args = [
                "--flag5",
            ],
        )""") in build
    assert ('    extra_enabled_features = [\n'
            '        ":conan_exe_link_flags",\n'
            '        ":conan_shared_link_flags",\n'
            '    ],') in build
    assert "conan_objc_flags" not in build
    assert 'builtin_sysroot = "/my/sysroot"' in build
    assert '"%sysroot%",' in build
    assert 'target_libc = "macosx"' in build  # rules_cc uses libtool as archiver
    assert '"-lc++",' in build


@pytest.mark.parametrize("build_type, flags", [("Debug", ['"-g",']),
                                                ("Release", ['"-O3",', '"-DNDEBUG",'])])
def test_bazel_toolchain_build_type(conanfile, build_type, flags):
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": _linux_x86_64})
    c.run(f"install . -pr:a profile -s build_type={build_type}")
    build = _build_file(c)
    for flag in flags:
        assert flag in build
    if build_type == "Debug":
        assert "NDEBUG" not in build


def test_bazel_toolchain_and_cross_compilation(conanfile):
    profile_host = _macos_x86_64.replace("arch=x86_64", "arch=armv8")
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": _macos_x86_64,
            "profile_host": profile_host})
    # The SDK path is defined to not call xcrun, which only exists in macOS
    c.run("install . -pr:b profile -pr:h profile_host -c tools.apple:sdk_path=/my/sdk")
    assert "and conan_bzl.rc (--config=conan-config)" in c.out
    bazelrc = c.load("conan/conan_bzl.rc")
    assert "build:conan-config --platforms=//conan/conan_toolchain:host_platform" in bazelrc
    assert "build:conan-config --host_platform=//conan/conan_toolchain:build_platform" in bazelrc
    assert "build:conan-config --strip=never" in bazelrc
    build = _build_file(c)
    assert textwrap.dedent("""\
        toolchain(
            name = "cc_toolchain",
            exec_compatible_with = [
                "@platforms//os:macos",
                "@platforms//cpu:x86_64",
            ],
            target_compatible_with = [
                "@platforms//os:macos",
                "@platforms//cpu:aarch64",
            ],""") in build
    assert 'cpu = "aarch64"' in build
    assert "macos_minimum_os" not in bazelrc
    assert '"-arch",\n        "arm64",' in build

    # A later native install overwrites the cross-building bazelrc, the Bazel helper would use it
    c.run("install . -pr:a profile")
    bazelrc = c.load("conan/conan_bzl.rc")
    assert "--platforms" not in bazelrc
    assert "--host_platform" not in bazelrc


def test_bazel_toolchain_android_cross_compilation(conanfile):
    profile_host = textwrap.dedent("""
    [settings]
    arch=armv8
    build_type=Release
    compiler=clang
    compiler.version=18
    compiler.libcxx=c++_shared
    compiler.cppstd=17
    os=Android
    os.api_level=24
    [conf]
    tools.android:ndk_path=/my/ndk
    """)
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": _linux_x86_64,
            "profile_host": profile_host})
    c.run("install . -pr:b profile -pr:h profile_host")
    build = _build_file(c)
    ndk_bin = "/my/ndk/toolchains/llvm/prebuilt/linux-x86_64/bin"
    assert f'"gcc": "{ndk_bin}/aarch64-linux-android24-clang"' in build
    assert f'"ar": "{ndk_bin}/llvm-ar"' in build
    assert '"/my/ndk",' in build
    assert "@platforms//os:android" in build
    assert "@platforms//cpu:aarch64" in build


def test_bazel_toolchain_android_no_ndk(conanfile):
    profile_host = textwrap.dedent("""
    [settings]
    arch=armv8
    build_type=Release
    compiler=clang
    compiler.version=18
    compiler.libcxx=c++_shared
    os=Android
    os.api_level=24
    """)
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": _linux_x86_64,
            "profile_host": profile_host})
    c.run("install . -pr:b profile -pr:h profile_host", assert_error=True)
    assert "You must provide a NDK path" in c.out


def test_toolchain_attributes():
    """
    Tests that the public attributes can be customized in the generate() method
    """
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.google import BazelToolchain, bazel_layout
    class ExampleConanIntegration(ConanFile):
        settings = "os", "arch", "build_type", "compiler"

        def layout(self):
            bazel_layout(self)

        def generate(self):
            bz = BazelToolchain(self)
            bz.extra_cflags = ["-cflag1"]
            bz.extra_cxxflags = ["-cxxflag1"]
            bz.extra_ldflags = ["-ldflag1"]
            bz.extra_defines = ["MYDEF"]
            bz.host_constraints.append("//my:constraint")
            bz.tool_paths = {"ar": "/my/ar"}
            bz.cxx_builtin_include_directories = ["/my/include"]
            bz.generate()
    """)
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": _linux_x86_64})
    c.run("install . -pr:a profile")
    build = _build_file(c)
    assert '"-cflag1",' in build
    assert '"-cxxflag1",' in build
    assert '"-ldflag1",' in build
    assert '"-DMYDEF",' in build
    assert '"//my:constraint",' in build
    assert '"ar": "/my/ar"' in build
    assert '"/my/include",' in build


def test_toolchain_include_directories_from_compiler(conanfile):
    """
    The system include directories are the ones reported by the compiler (gcc -E -v)
    """
    output = textwrap.dedent("""        #include <...> search starts here:
         /usr/include/c++/13
         /opt/gcc/lib/gcc/x86_64-linux-gnu/12/../../../../include/c++/12
         /usr/include
        End of search list.
        """)
    commands = []
    isfile = os.path.isfile

    def fake_run(conanfile, command, stdout=None, stderr=None, **kwargs):
        commands.append(command)
        stderr.write(output)
        return 0

    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": _linux_x86_64})
    # The compiler path "exists" and it reports the include directories
    with mock.patch("conan.tools.google.toolchain.os.path.isfile",
                    side_effect=lambda p: p == "/opt/gcc/bin/gcc" or isfile(p)),             mock.patch("conan.internal.model.conan_file.ConanFile.run", autospec=True,
                       side_effect=fake_run):
        c.run("install . -pr:a profile")
    assert "-m64" in commands[0]
    build = _build_file(c)
    assert '"/usr/include/c++/13",' in build
    assert '"/opt/gcc/include/c++/12",' in build  # normalized
    assert '"/usr/lib",' not in build  # default ones are not needed


def test_toolchain_cpp_tool_follows_gcc(conanfile):
    """
    The C preprocessor is the one of the profile compiler (cross prefix and version), not the
    one in the PATH of the machine
    """
    profile = _linux_x86_64.replace("/opt/gcc/bin/gcc", "/opt/gcc/bin/aarch64-linux-gnu-gcc-12")
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": profile})
    c.run("install . -pr:a profile")
    assert '"cpp": "/opt/gcc/bin/aarch64-linux-gnu-cpp-12"' in _build_file(c)


def test_toolchain_tool_not_found(conanfile):
    """
    A required tool that is not found points to a failing binary, so the user is warned
    """
    profile = _linux_x86_64.replace('"c": "/opt/gcc/bin/gcc"', '"c": "my-missing-cc"')
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": profile})
    c.run("install . -pr:a profile")
    assert "WARN: BazelToolchain: the 'gcc' tool ('my-missing-cc') was not found" in c.out
    assert '"gcc": "/bin/false"' in _build_file(c)


def test_toolchain_generates_in_generators_folder_not_in_cwd():
    conanfile = textwrap.dedent("""
    import os
    import tempfile
    from conan import ConanFile
    from conan.tools.google import BazelToolchain, bazel_layout
    class ExampleConanIntegration(ConanFile):
        settings = "os", "arch", "build_type", "compiler"

        def layout(self):
            bazel_layout(self)

        def generate(self):
            cwd = os.getcwd()
            os.chdir(tempfile.mkdtemp())
            try:
                BazelToolchain(self).generate()
            finally:
                os.chdir(cwd)
    """)
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": _linux_x86_64})
    c.run("install . -pr:a profile")
    assert os.path.exists(os.path.join(c.current_folder, "conan", "BUILD.bazel"))
    assert os.path.exists(os.path.join(c.current_folder, "conan", "conan_toolchain.MODULE.bazel"))
    assert os.path.exists(os.path.join(c.current_folder, "conan", "conan_toolchain",
                                       "BUILD.bazel"))
    assert os.path.exists(os.path.join(c.current_folder, "conan", "conan_bzl.rc"))


def test_toolchain_no_cc_toolchain():
    """
    With generate_cc_toolchain = False, Bazel uses its auto-configured toolchain and the Conan
    flags are passed in the conan_bzl.rc file
    """
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.google import BazelToolchain, bazel_layout
    class ExampleConanIntegration(ConanFile):
        settings = "os", "arch", "build_type", "compiler"

        def layout(self):
            bazel_layout(self)

        def generate(self):
            bz = BazelToolchain(self)
            bz.generate_cc_toolchain = False
            bz.generate()
    """)
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": _linux_x86_64 + 'tools.build:cxxflags=["--flag1"]\n'})
    c.run("install . -pr:a profile")
    assert os.listdir(os.path.join(c.current_folder, "conan", "conan_toolchain")) == \
        ["BUILD.bazel"]
    build = _build_file(c)
    assert "cc_toolchain" not in build
    assert "host_platform" in build
    assert "register_toolchains" not in c.load("conan/conan_toolchain.MODULE.bazel")
    bazelrc = c.load("conan/conan_bzl.rc")
    assert "--platforms" not in bazelrc
    assert "build:conan-config --compilation_mode=opt" in bazelrc
    assert "build:conan-config --copt=-O3" in bazelrc
    assert "build:conan-config --cxxopt=-std=gnu++17" in bazelrc
    assert "build:conan-config --cxxopt=--flag1" in bazelrc
    assert "build:conan-config --linkopt=-m64" in bazelrc


def test_toolchain_msvc():
    """
    MSVC uses Bazel auto-configured toolchain by default, and the flags are passed via bazelrc
    """
    profile = textwrap.dedent("""
    [settings]
    arch=x86_64
    build_type=Release
    compiler=msvc
    compiler.cppstd=17
    compiler.runtime=dynamic
    compiler.version=194
    os=Windows
    """)
    conanfile = GenConanfile().with_settings("os", "arch", "build_type", "compiler")\
        .with_generator("BazelToolchain")
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": profile})
    c.run("install . -pr:a profile")
    build = c.load("conan_toolchain/BUILD.bazel")
    assert "cc_toolchain" not in build
    assert "@platforms//os:windows" in build
    bazelrc = c.load("conan_bzl.rc")
    assert "build:conan-config --cxxopt=/std:c++17" in bazelrc
    # The runtime is managed by Bazel features, /MD (/MDd if "dbg") by default
    assert "MD" not in bazelrc
    assert "static_link_msvcrt" not in bazelrc
    assert "--platforms" not in bazelrc
    assert "register_toolchains" not in c.load("conan_toolchain.MODULE.bazel")

    c.run("install . -pr:a profile -s compiler.runtime=static -s build_type=Debug")
    bazelrc = c.load("conan_bzl.rc")
    assert "build:conan-config --compilation_mode=dbg" in bazelrc
    assert "build:conan-config --features=static_link_msvcrt" in bazelrc
    assert "MT" not in bazelrc
    # /Zi shares one .pdb between the parallel cl.exe of Bazel (C1041), /Z7 does not
    assert "build:conan-config --copt=-Z7" in bazelrc
    assert "-Zi" not in bazelrc


def test_toolchain_msvc_bazelrc_quoting():
    """
    Bazel splits each bazelrc line by spaces, so the flags that contain them have to be quoted
    """
    profile = textwrap.dedent("""
    [settings]
    arch=x86_64
    build_type=Release
    compiler=msvc
    compiler.cppstd=17
    compiler.runtime=dynamic
    compiler.version=194
    os=Windows
    [conf]
    tools.build:defines=["GREETING=hello world", "PLAIN=1"]
    """)
    conanfile = GenConanfile().with_settings("os", "arch", "build_type", "compiler")\
        .with_generator("BazelToolchain")
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": profile})
    c.run("install . -pr:a profile")
    bazelrc = c.load("conan_bzl.rc")
    assert 'build:conan-config "--copt=-DGREETING=hello world"' in bazelrc
    assert "build:conan-config --copt=-DPLAIN=1" in bazelrc


def test_toolchain_msvc_repo_env_path_with_spaces():
    """
    The Visual Studio installation path has spaces by default (C:/Program Files/...)
    """
    profile = textwrap.dedent("""
    [settings]
    arch=x86_64
    build_type=Release
    compiler=msvc
    compiler.cppstd=17
    compiler.runtime=dynamic
    compiler.version=194
    os=Windows
    [conf]
    tools.microsoft.msbuild:installation_path=C:/Program Files/Microsoft Visual Studio/2022/Community
    """)
    conanfile = GenConanfile().with_settings("os", "arch", "build_type", "compiler")\
        .with_generator("BazelToolchain")
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": profile})
    c.run("install . -pr:a profile")
    bazelrc = c.load("conan_bzl.rc")
    assert ('build:conan-config "--repo_env=BAZEL_VC=C:/Program Files/Microsoft Visual Studio/'
            '2022/Community/VC"') in bazelrc


def test_toolchain_clang_cl_not_supported():
    profile = textwrap.dedent("""
    [settings]
    arch=x86_64
    build_type=Release
    compiler=clang
    compiler.version=19
    compiler.cppstd=17
    compiler.runtime=dynamic
    compiler.runtime_version=v143
    os=Windows
    """)
    conanfile = GenConanfile().with_settings("os", "arch", "build_type", "compiler")        .with_generator("BazelToolchain")
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": profile})
    c.run("install . -pr:a profile", assert_error=True)
    assert "BazelToolchain: clang-cl is not supported yet" in c.out


def test_toolchain_ios_cross_compilation(conanfile):
    """
    rules_cc adds -mmacosx-version-min to every "macosx" libc toolchain, which collides with the
    Conan -mios-version-min flag
    """
    profile_host = textwrap.dedent("""
    [settings]
    arch=armv8
    build_type=Release
    compiler=apple-clang
    compiler.version=17
    compiler.libcxx=libc++
    os=iOS
    os.version=15.0
    os.sdk=iphoneos
    """)
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": _macos_x86_64,
            "profile_host": profile_host})
    c.run("install . -pr:b profile -pr:h profile_host -c tools.apple:sdk_path=/my/sdk")
    build = _build_file(c)
    assert 'target_libc = "macosx"' in build
    assert '"-mios-version-min=15.0",' in build
    bazelrc = c.load("conan/conan_bzl.rc")
    assert "build:conan-config --features=-macos_minimum_os" in bazelrc


def test_recipe_without_shared_option():
    """
    A recipe without shared/fPIC options does not add -fPIC
    """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile().with_settings("os", "arch", "build_type", "compiler")
            .with_generator("BazelToolchain"),
            "profile": _linux_x86_64})
    c.run("install . -pr:a profile")
    # Without bazel_layout, the generators folder is the Bazel workspace root
    assert 'register_toolchains("//conan_toolchain:cc_toolchain")' in \
           c.load("conan_toolchain.MODULE.bazel")
    assert "-fPIC" not in c.load("conan_toolchain/BUILD.bazel")


def test_linker_flags_do_not_mutate_conf():
    """
    Generating the toolchain must not append exe flags or linker scripts onto
    tools.build:sharedlinkflags. Generating it twice gives the same result.
    """
    profile = textwrap.dedent("""
    [conf]
    tools.build:sharedlinkflags=["--shared"]
    tools.build:exelinkflags=["--exe"]
    tools.build:linker_scripts=["myscript.sh"]
    tools.build:defines=["MYDEF"]
    """)
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.files import load
    from conan.tools.google import BazelToolchain
    class ExampleConanIntegration(ConanFile):
        settings = "os", "arch", "build_type", "compiler"

        def generate(self):
            bz = BazelToolchain(self)
            bz.generate()
            first = load(self, "conan_toolchain/BUILD.bazel")
            bz.generate()
            second = load(self, "conan_toolchain/BUILD.bazel")
            assert first == second
            shared = " ".join(self.conf.get("tools.build:sharedlinkflags"))
            defines = " ".join(self.conf.get("tools.build:defines"))
            self.output.info(f"CONF {shared} || {defines}")
    """)
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile_base": _linux_x86_64,
            "profile": "include(profile_base)\n" + profile})
    c.run("install . -pr:a profile")
    assert "CONF --shared || MYDEF" in c.out


def test_no_compiler_error():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile().with_settings("os", "arch")
            .with_generator("BazelToolchain")})
    c.run("install .", assert_error=True)
    assert "BazelToolchain needs 'settings.compiler', but it is not defined" in c.out


def test_generators_folder_outside_workspace():
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    class ExampleConanIntegration(ConanFile):
        settings = "os", "arch", "build_type", "compiler"
        generators = "BazelToolchain"

        def layout(self):
            self.folders.source = "src"
            self.folders.generators = "gen"
    """)
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": _linux_x86_64})
    c.run("install . -pr:a profile", assert_error=True)
    assert "must be inside the Bazel workspace" in c.out
