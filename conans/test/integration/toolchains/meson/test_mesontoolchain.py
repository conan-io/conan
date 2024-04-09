import os
import platform
import textwrap

import pytest

from conan.tools.meson import MesonToolchain
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_apple_meson_keep_user_custom_flags():
    default = textwrap.dedent("""
    [settings]
    os=Macos
    arch=x86_64
    compiler=apple-clang
    compiler.version=12.0
    compiler.libcxx=libc++
    build_type=Release
    """)

    cross = textwrap.dedent("""
    [settings]
    os = iOS
    os.version = 10.0
    os.sdk = iphoneos
    arch = armv8
    compiler = apple-clang
    compiler.version = 12.0
    compiler.libcxx = libc++

    [conf]
    tools.apple:sdk_path=/my/sdk/path
    """)

    _conanfile_py = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.meson import MesonToolchain

    class App(ConanFile):
        settings = "os", "arch", "compiler", "build_type"

        def generate(self):
            tc = MesonToolchain(self)
            # Customized apple flags
            tc.apple_arch_flag = ['-arch', 'myarch']
            tc.apple_isysroot_flag = ['-isysroot', '/other/sdk/path']
            tc.apple_min_version_flag = ['-otherminversion=10.7']
            tc.generate()
    """)

    t = TestClient()
    t.save({"conanfile.py": _conanfile_py,
            "build_prof": default,
            "host_prof": cross})

    t.run("install . -pr:h host_prof -pr:b build_prof")
    # Checking that the global conanbuild aggregator includes conanbuildenv-xxx file
    # it should have been generated by implicit VirtualBuildEnv generator
    env_file = t.load("conanbuild.sh")
    assert "conanbuildenv" in env_file
    content = t.load(MesonToolchain.cross_filename)
    assert "c_args = ['-isysroot', '/other/sdk/path', '-arch', 'myarch', '-otherminversion=10.7']" in content
    assert "c_link_args = ['-isysroot', '/other/sdk/path', '-arch', 'myarch', '-otherminversion=10.7']" in content
    assert "cpp_args = ['-isysroot', '/other/sdk/path', '-arch', 'myarch', '-otherminversion=10.7', '-stdlib=libc++']" in content
    assert "cpp_link_args = ['-isysroot', '/other/sdk/path', '-arch', 'myarch', '-otherminversion=10.7', '-stdlib=libc++']" in content


def test_extra_flags_via_conf():
    profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        compiler=gcc
        compiler.version=9
        compiler.cppstd=17
        compiler.libcxx=libstdc++
        build_type=Release

        [buildenv]
        CFLAGS=-flag0 -other=val
        CXXFLAGS=-flag0 -other=val
        LDFLAGS=-flag0 -other=val

        [conf]
        tools.build:cxxflags=["-flag1", "-flag2"]
        tools.build:cflags=["-flag3", "-flag4"]
        tools.build:sharedlinkflags+=["-flag5"]
        tools.build:exelinkflags+=["-flag6"]
   """)
    t = TestClient()
    t.save({"conanfile.txt": "[generators]\nMesonToolchain",
            "profile": profile})

    t.run("install . -pr:h=profile -pr:b=profile")
    content = t.load(MesonToolchain.native_filename)
    assert "cpp_args = ['-flag0', '-other=val', '-flag1', '-flag2', '-D_GLIBCXX_USE_CXX11_ABI=0']" in content
    assert "c_args = ['-flag0', '-other=val', '-flag3', '-flag4']" in content
    assert "c_link_args = ['-flag0', '-other=val', '-flag5', '-flag6']" in content
    assert "cpp_link_args = ['-flag0', '-other=val', '-flag5', '-flag6']" in content


def test_linker_scripts_via_conf():
    profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        compiler=gcc
        compiler.version=9
        compiler.cppstd=17
        compiler.libcxx=libstdc++
        build_type=Release

        [buildenv]
        LDFLAGS=-flag0 -other=val

        [conf]
        tools.build:sharedlinkflags+=["-flag5"]
        tools.build:exelinkflags+=["-flag6"]
        tools.build:linker_scripts+=["/linker/scripts/flash.ld", "/linker/scripts/extra_data.ld"]
   """)
    t = TestClient()
    t.save({"conanfile.txt": "[generators]\nMesonToolchain",
            "profile": profile})

    t.run("install . -pr:b=profile -pr=profile")
    content = t.load(MesonToolchain.native_filename)
    assert "c_link_args = ['-flag0', '-other=val', '-flag5', '-flag6', '-T\"/linker/scripts/flash.ld\"', '-T\"/linker/scripts/extra_data.ld\"']" in content
    assert "cpp_link_args = ['-flag0', '-other=val', '-flag5', '-flag6', '-T\"/linker/scripts/flash.ld\"', '-T\"/linker/scripts/extra_data.ld\"']" in content


def test_correct_quotes():
    profile = textwrap.dedent("""
       [settings]
       os=Windows
       arch=x86_64
       compiler=gcc
       compiler.version=9
       compiler.cppstd=17
       compiler.libcxx=libstdc++11
       build_type=Release
       """)
    t = TestClient()
    t.save({"conanfile.txt": "[generators]\nMesonToolchain",
            "profile": profile})

    t.run("install . -pr:h=profile -pr:b=profile")
    content = t.load(MesonToolchain.native_filename)
    assert "cpp_std = 'c++17'" in content
    assert "backend = 'ninja'" in content
    assert "buildtype = 'release'" in content


def test_c_std():
    profile = textwrap.dedent("""
       [settings]
       os=Windows
       arch=x86_64
       compiler=gcc
       compiler.version=9
       compiler.cstd=11
       build_type=Release
       """)
    t = TestClient()
    t.save({"conanfile.py": GenConanfile().with_settings("os", "compiler", "build_type", "arch")
                                          .with_generator("MesonToolchain")
                                          .with_class_attribute("languages='C'"),
            "profile": profile})

    t.run("install . -pr:h=profile -pr:b=profile")
    content = t.load(MesonToolchain.native_filename)
    assert "c_std = 'c11'" in content
    assert "backend = 'ninja'" in content
    assert "buildtype = 'release'" in content


def test_deactivate_nowrap():
    # https://github.com/conan-io/conan/issues/10671
    t = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.meson import MesonToolchain
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            def generate(self):
                tc = MesonToolchain(self)
                tc.project_options.pop("wrap_mode")
                tc.generate()
        """)
    t.save({"conanfile.py": conanfile})
    t.run("install .")
    content = t.load(MesonToolchain.native_filename)
    assert "wrap_mode " not in content
    assert "nofallback" not in content


@pytest.mark.skipif(platform.system() != "Windows", reason="requires Win")
@pytest.mark.parametrize("build_type,runtime,vscrt", [
    ("Debug", "dynamic", "mdd"),
    ("Debug", "static", "mtd"),
    ("Release", "dynamic", "md"),
    ("Release", "static", "mt")
])
def test_clang_cl_vscrt(build_type, runtime, vscrt):
    profile = textwrap.dedent(f"""
        [settings]
        os=Windows
        arch=x86_64
        build_type={build_type}
        compiler=clang
        compiler.runtime={runtime}
        compiler.runtime_version=v143
        compiler.version=16

        [conf]
        tools.cmake.cmaketoolchain:generator=Visual Studio 17

        [buildenv]
        CC=clang-cl
        CXX=clang-cl
   """)
    t = TestClient()
    t.save({"conanfile.txt": "[generators]\nMesonToolchain",
            "profile": profile})

    t.run("install . -pr:h=profile -pr:b=profile")
    content = t.load(MesonToolchain.native_filename)
    assert f"b_vscrt = '{vscrt}'" in content


def test_env_vars_from_build_require():
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    import os

    class HelloConan(ConanFile):
        name = 'hello_compiler'
        version = '1.0'
        def package_info(self):
            self.buildenv_info.define("CC", "CC_VALUE")
            self.buildenv_info.define("CC_LD", "CC_LD_VALUE")
            self.buildenv_info.define("CXX", "CXX_VALUE")
            self.buildenv_info.define("CXX_LD", "CXX_LD_VALUE")
            self.buildenv_info.define("AR", "AR_VALUE")
            self.buildenv_info.define("STRIP", "STRIP_VALUE")
            self.buildenv_info.define("AS", "AS_VALUE")
            self.buildenv_info.define("WINDRES", "WINDRES_VALUE")
            self.buildenv_info.define("PKG_CONFIG", "PKG_CONFIG_VALUE")
            self.buildenv_info.define("LD", "LD_VALUE")
    """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create .")

    conanfile = textwrap.dedent("""
    from conan import ConanFile
    class HelloConan(ConanFile):
        name = 'consumer'
        version = '1.0'
        generators = "MesonToolchain"
        settings = "os", "arch", "compiler", "build_type"

        def requirements(self):
            self.tool_requires("hello_compiler/1.0", )
    """)
    # Now, let's check how all the build env variables are applied at consumer side
    client.save({"conanfile.py": conanfile})
    client.run("install . -pr:h=default -pr:b=default")
    content = client.load("conan_meson_native.ini")
    assert "c = 'CC_VALUE'" in content
    assert "cpp = 'CXX_VALUE'" in content
    assert "ld = 'LD_VALUE'" in content
    assert "c_ld = 'CC_LD_VALUE'" in content
    assert "cpp_ld = 'CXX_LD_VALUE'" in content
    assert "ar = 'AR_VALUE'" in content
    assert "strip = 'STRIP_VALUE'" in content
    assert "as = 'AS_VALUE'" in content
    assert "windres = 'WINDRES_VALUE'" in content
    assert "pkgconfig = 'PKG_CONFIG_VALUE'" in content
    assert "pkg-config = 'PKG_CONFIG_VALUE'" in content


def test_check_c_cpp_ld_list_formats():
    # Issue related: https://github.com/conan-io/conan/issues/14028
    profile = textwrap.dedent("""
       [settings]
       os=Windows
       arch=x86_64
       compiler=gcc
       compiler.version=9
       compiler.cppstd=17
       compiler.libcxx=libstdc++11
       build_type=Release
       [buildenv]
       CC=aarch64-poky-linux-gcc  -mcpu=cortex-a53 -march=armv8-a+crc+crypto
       CXX=aarch64-poky-linux-g++  -mcpu=cortex-a53 -march=armv8-a+crc+crypto
       LD=aarch64-poky-linux-ld  --sysroot=/opt/sysroots/cortexa53-crypto-poky-linux
       """)
    t = TestClient()
    t.save({"conanfile.txt": "[generators]\nMesonToolchain",
            "profile": profile})
    t.run("install . -pr:h=profile -pr:b=profile")
    content = t.load(MesonToolchain.native_filename)
    assert "c = ['aarch64-poky-linux-gcc', '-mcpu=cortex-a53', '-march=armv8-a+crc+crypto']" in content
    assert "cpp = ['aarch64-poky-linux-g++', '-mcpu=cortex-a53', '-march=armv8-a+crc+crypto']" in content
    assert "ld = ['aarch64-poky-linux-ld', '--sysroot=/opt/sysroots/cortexa53-crypto-poky-linux']" in content


def test_check_pkg_config_paths():
    # Issue: https://github.com/conan-io/conan/issues/12342
    # Issue: https://github.com/conan-io/conan/issues/14935
    t = TestClient()
    t.save({"conanfile.txt": "[generators]\nMesonToolchain"})
    t.run("install .")
    content = t.load(MesonToolchain.native_filename)
    assert f"pkg_config_path = '{t.current_folder}'" in content
    assert f"build.pkg_config_path = " not in content
    conanfile = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.meson import MesonToolchain
    class Pkg(ConanFile):
        settings = "os", "compiler", "arch", "build_type"
        def generate(self):
            tc = MesonToolchain(self)
            tc.build_pkg_config_path = os.path.join(self.generators_folder, "build")
            tc.generate()
    """)
    t.save({"conanfile.py": conanfile}, clean_first=True)
    t.run("install .")
    content = t.load(MesonToolchain.native_filename)
    base_folder = t.current_folder
    assert f"pkg_config_path = '{base_folder}'" in content
    assert f"build.pkg_config_path = '{os.path.join(base_folder, 'build')}'" in content



def test_toolchain_and_compilers_build_context():
    """
    Tests how MesonToolchain manages the build context profile if the build profile is
    specifying another compiler path (using conf).

    It should create both native and cross files.

    Issue related: https://github.com/conan-io/conan/issues/15878
    """
    host = textwrap.dedent("""
    [settings]
    arch=armv8
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)
    build = textwrap.dedent("""
    [settings]
    os=Linux
    arch=x86_64
    compiler=clang
    compiler.version=12
    compiler.libcxx=libc++
    compiler.cppstd=11

    [conf]
    tools.build:compiler_executables={"asm": "clang", "c": "clang", "cpp": "clang++"}
    """)
    conanfile = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.files import replace_in_file
    class helloRecipe(ConanFile):
        name = "hello"
        version = "1.0.0"
        package_type = "application"
        # Binary configuration
        settings = "os", "compiler", "build_type", "arch"
        generators = "MesonToolchain"

        def build(self):
            native_path = os.path.join(self.generators_folder, "conan_meson_native.ini")
            cross_path = os.path.join(self.generators_folder, "conan_meson_cross.ini")
            assert os.path.exists(cross_path)  # sanity check
            assert os.path.exists(native_path)  # sanity check
            # This should not raise anything!! Notice the strict=True
            replace_in_file(self, cross_path, 'c = gcc', "#Hey", strict=True)
            replace_in_file(self, cross_path, 'cpp = g++', "#Hey", strict=True)
            replace_in_file(self, native_path, 'c = clang', "#Hey", strict=True)
            replace_in_file(self, native_path, 'cpp = clang++', "#Hey", strict=True)
    """)
    client = TestClient()
    client.save({
        "host": host,
        "build": build,
        "conanfile.py": conanfile
    })
    client.run("build . -pr:h host -pr:b build")


def test_toolchain_and_compilers_build_context():
    """
    Tests how MesonToolchain manages the build context profile if the build profile is
    specifying another compiler path (using conf).

    It should create both native and cross files.

    Issue related: https://github.com/conan-io/conan/issues/15878
    """
    host = textwrap.dedent("""
    [settings]
    arch=armv8
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux

    [conf]
    tools.build:compiler_executables={"c": "gcc", "cpp": "g++"}
    """)
    build = textwrap.dedent("""
    [settings]
    os=Linux
    arch=x86_64
    compiler=clang
    compiler.version=12
    compiler.libcxx=libc++
    compiler.cppstd=11

    [conf]
    tools.build:compiler_executables={"c": "clang", "cpp": "clang++"}
    """)
    tool = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.files import load

    class toolRecipe(ConanFile):
        name = "tool"
        version = "1.0"
        # Binary configuration
        settings = "os", "compiler", "build_type", "arch"
        generators = "MesonToolchain"

        def build(self):
            toolchain = os.path.join(self.generators_folder, "conan_meson_native.ini")
            content = load(self, toolchain)
            assert "c = 'clang'" in content
            assert "cpp = 'clang++'" in content
    """)
    consumer = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.files import load

    class consumerRecipe(ConanFile):
        name = "consumer"
        version = "1.0"
        # Binary configuration
        settings = "os", "compiler", "build_type", "arch"
        generators = "MesonToolchain"
        tool_requires = "tool/1.0"

        def build(self):
            toolchain = os.path.join(self.generators_folder, "conan_meson_cross.ini")
            content = load(self, toolchain)
            assert "c = 'gcc'" in content
            assert "cpp = 'g++'" in content
    """)
    client = TestClient()
    client.save({
        "host": host,
        "build": build,
        "tool/conanfile.py": tool,
        "consumer/conanfile.py": consumer
    })
    client.run("export tool")
    client.run("create consumer -pr:h host -pr:b build --build=missing")


def test_subproject_options():
    t = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.meson import MesonToolchain
        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            def generate(self):
                tc = MesonToolchain(self)
                tc.subproject_options["subproject1"] = [{"option1": "enabled"}, {"option2": "disabled"}]
                tc.subproject_options["subproject2"] = [{"option3": "enabled"}]
                tc.subproject_options["subproject2"].append({"option4": "disabled"})
                tc.generate()
        """)
    t.save({"conanfile.py": conanfile})
    t.run("install .")
    content = t.load(MesonToolchain.native_filename)
    assert "[subproject1:project options]" in content
    assert "[subproject2:project options]" in content
    assert "option1 = 'enabled'" in content
    assert "option2 = 'disabled'" in content
    assert "option3 = 'enabled'" in content
    assert "option4 = 'disabled'" in content
