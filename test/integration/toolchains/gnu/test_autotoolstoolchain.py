import os
import platform
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conans.util.files import save, load


def test_extra_flags_via_conf():
    os_ = platform.system()
    os_ = "Macos" if os_ == "Darwin" else os_

    profile = textwrap.dedent("""
        [settings]
        os=%s
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        arch=armv8
        build_type=Release

        [conf]
        tools.build:cxxflags=["--flag1", "--flag2"]
        tools.build:cflags+=["--flag3", "--flag4"]
        tools.build:sharedlinkflags+=["--flag5"]
        tools.build:exelinkflags+=["--flag6"]
        tools.build:defines+=["DEF1", "DEF2"]
        """ % os_)
    client = TestClient()
    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("AutotoolsToolchain")
    client.save({"conanfile.py": conanfile,
                "profile": profile})
    client.run("install . --profile:build=profile --profile:host=profile")
    toolchain = client.load("conanautotoolstoolchain{}".format('.bat' if os_ == "Windows" else '.sh'))
    if os_ == "Windows":
        assert 'set "CPPFLAGS=%CPPFLAGS% -DNDEBUG -DDEF1 -DDEF2"' in toolchain
        assert 'set "CXXFLAGS=%CXXFLAGS% -O3 --flag1 --flag2"' in toolchain
        assert 'set "CFLAGS=%CFLAGS% -O3 --flag3 --flag4"' in toolchain
        assert 'set "LDFLAGS=%LDFLAGS% --flag5 --flag6"' in toolchain
    else:
        assert 'export CPPFLAGS="$CPPFLAGS -DNDEBUG -DDEF1 -DDEF2"' in toolchain
        assert 'export CXXFLAGS="$CXXFLAGS -O3 --flag1 --flag2"' in toolchain
        assert 'export CFLAGS="$CFLAGS -O3 --flag3 --flag4"' in toolchain
        assert 'export LDFLAGS="$LDFLAGS --flag5 --flag6"' in toolchain


def test_extra_flags_order():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.gnu import AutotoolsToolchain

        class Conan(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os", "arch", "build_type"
            def generate(self):
                at = AutotoolsToolchain(self)
                at.extra_cxxflags = ["extra_cxxflags"]
                at.extra_cflags = ["extra_cflags"]
                at.extra_ldflags = ["extra_ldflags"]
                at.extra_defines = ["extra_defines"]
                at.generate()
        """)
    profile = textwrap.dedent("""
        include(default)
        [conf]
        tools.build:cxxflags+=['cxxflags']
        tools.build:cflags+=['cflags']
        tools.build:sharedlinkflags+=['sharedlinkflags']
        tools.build:exelinkflags+=['exelinkflags']
        tools.build:defines+=['defines']
        """)
    client.save({"conanfile.py": conanfile, "profile": profile})
    client.run('install . -pr=./profile')
    toolchain = client.load("conanautotoolstoolchain{}".format('.bat' if platform.system() == "Windows" else '.sh'))

    assert '-Dextra_defines -Ddefines' in toolchain
    assert 'extra_cxxflags cxxflags' in toolchain
    assert 'extra_cflags cflags' in toolchain
    assert 'extra_ldflags sharedlinkflags exelinkflags' in toolchain


def test_autotools_custom_environment():
    client = TestClient()
    conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.gnu import AutotoolsToolchain

            class Conan(ConanFile):
                settings = "os"
                def generate(self):
                    at = AutotoolsToolchain(self)
                    env = at.environment()
                    env.define("FOO", "BAR")
                    at.generate(env)
            """)

    client.save({"conanfile.py": conanfile})
    client.run("install . -s:b os=Linux -s:h os=Linux")
    content = load(os.path.join(client.current_folder,  "conanautotoolstoolchain.sh"))
    assert 'export FOO="BAR"' in content


def test_linker_scripts_via_conf():
    os_ = platform.system()
    os_ = "Macos" if os_ == "Darwin" else os_

    profile = textwrap.dedent("""
        [settings]
        os=%s
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        arch=armv8
        build_type=Release

        [conf]
        tools.build:sharedlinkflags+=["--flag5"]
        tools.build:exelinkflags+=["--flag6"]
        tools.build:linker_scripts+=["/linker/scripts/flash.ld", "/linker/scripts/extra_data.ld"]
        """ % os_)
    client = TestClient()
    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("AutotoolsToolchain")
    client.save({"conanfile.py": conanfile,
                "profile": profile})
    client.run("install . --profile:build=profile --profile:host=profile")
    toolchain = client.load("conanautotoolstoolchain{}".format('.bat' if os_ == "Windows" else '.sh'))
    if os_ == "Windows":
        assert 'set "LDFLAGS=%LDFLAGS% --flag5 --flag6 -T\'/linker/scripts/flash.ld\' -T\'/linker/scripts/extra_data.ld\'"' in toolchain
    else:
        assert 'export LDFLAGS="$LDFLAGS --flag5 --flag6 -T\'/linker/scripts/flash.ld\' -T\'/linker/scripts/extra_data.ld\'"' in toolchain


def test_not_none_values():

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.gnu import AutotoolsToolchain

        class Foo(ConanFile):
            name = "foo"
            version = "1.0"

            def generate(self):
                tc = AutotoolsToolchain(self)
                assert None not in tc.defines
                assert None not in tc.cxxflags
                assert None not in tc.cflags
                assert None not in tc.ldflags

    """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("install .")


def test_set_prefix():

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.gnu import AutotoolsToolchain
        from conan.tools.layout import basic_layout


        class Foo(ConanFile):
            name = "foo"
            version = "1.0"
            def layout(self):
                basic_layout(self)
            def generate(self):
                at_toolchain = AutotoolsToolchain(self, prefix="/somefolder")
                at_toolchain.generate()
    """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("install .")
    conanbuild = client.load(os.path.join(client.current_folder, "build", "conan", "conanbuild.conf"))
    assert "--prefix=/somefolder" in conanbuild
    assert conanbuild.count("--prefix") == 1


def test_unknown_compiler():
    client = TestClient()
    settings = load(client.cache.settings_path)
    settings = settings.replace("gcc:", "xlc:\n    gcc:", 1)
    save(client.cache.settings_path, settings)
    client.save({"conanfile.py": GenConanfile().with_settings("compiler", "build_type")
                                               .with_generator("AutotoolsToolchain")})
    # this used to crash, because of build_type_flags in AutotoolsToolchain returning empty string
    client.run("install . -s compiler=xlc")
    assert "conanfile.py: Generator 'AutotoolsToolchain' calling 'generate()'" in client.out


def test_toolchain_and_compilers_build_context():
    """
    Tests how AutotoolsToolchain manages the build context profile if the build profile is
    specifying another compiler path (using conf)

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
    tools.build:compiler_executables={"c": "gcc", "cpp": "g++", "rc": "windres"}
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
        generators = "AutotoolsToolchain"

        def build(self):
            toolchain = os.path.join(self.generators_folder, "conanautotoolstoolchain.sh")
            content = load(self, toolchain)
            assert 'export CC="clang"' in content
            assert 'export CXX="clang++"' in content
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
        generators = "AutotoolsToolchain"
        tool_requires = "tool/1.0"

        def build(self):
            toolchain = os.path.join(self.generators_folder, "conanautotoolstoolchain.sh")
            content = load(self, toolchain)
            assert 'export CC="gcc"' in content
            assert 'export CXX="g++"' in content
            assert 'export RC="windres"' in content
            # Issue: https://github.com/conan-io/conan/issues/15486
            assert 'export CC_FOR_BUILD="clang"' in content
            assert 'export CXX_FOR_BUILD="clang++"' in content
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
