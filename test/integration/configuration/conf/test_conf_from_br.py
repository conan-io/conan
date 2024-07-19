import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_basic():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):

            def package_info(self):
                self.conf_info.define_path("tools.android:ndk_path", "MY-NDK!!!")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=android_ndk --version=1.0")

    consumer = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"
            build_requires = "android_ndk/1.0"

            def generate(self):
                self.output.info("NDK: %s" % self.conf.get("tools.android:ndk_path"))
        """)
    # CMakeToolchain needs compiler definition
    linux_profile = textwrap.dedent("""
        [settings]
        os = Linux
        arch = x86_64
        compiler = gcc
        compiler.version = 4.9
        compiler.libcxx = libstdc++
        """)
    android_profile = textwrap.dedent("""
        include(linux)
        [conf]
        tools.android:ndk_path=MY-SYSTEM-NDK!!!
        """)
    client.save({"conanfile.py": consumer,
                 "linux": linux_profile,
                 "android": android_profile}, clean_first=True)

    client.run("install . -pr=linux")
    assert "conanfile.py: NDK: MY-NDK!!!" in client.out

    client.run("install . -pr:b=default -pr:h=android")
    assert "conanfile.py: NDK: MY-SYSTEM-NDK!!!" in client.out


def test_basic_conf_through_cli():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):

            def package_info(self):
                self.output.info("NDK build: %s" % self.conf.get("tools.android:ndk_path"))
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=android_ndk --version=1.0")

    consumer = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"
            build_requires = "android_ndk/1.0"

            def generate(self):
                self.output.info("NDK host: %s" % self.conf.get("tools.android:ndk_path"))
        """)
    # CMakeToolchain needs compiler definition
    linux_profile = textwrap.dedent("""
        [settings]
        os = Linux
        arch = x86_64
        compiler = gcc
        compiler.version = 4.9
        compiler.libcxx = libstdc++
        """)
    android_profile = textwrap.dedent("""
        include(linux)
        [conf]
        tools.android:ndk_path=MY-SYSTEM-NDK!!!
        """)
    client.save({"conanfile.py": consumer,
                 "linux": linux_profile,
                 "android": android_profile}, clean_first=True)
    client.run('install . -c:b=tools.android:ndk_path="MY-NDK!!!" '
               '-c:h=tools.android:ndk_path="MY-SYSTEM-NDK!!!" -pr:b=default -pr:h=android')
    assert "android_ndk/1.0: NDK build: MY-NDK!!!" in client.out
    assert "conanfile.py: NDK host: MY-SYSTEM-NDK!!!" in client.out


def test_declared_generators_get_conf():
    # https://github.com/conan-io/conan/issues/9571
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def package_info(self):
                self.conf_info.append("tools.cmake.cmaketoolchain:user_toolchain",
                                      "mytoolchain.cmake")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=mytool --version=1.0")

    consumer = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"
            build_requires = "mytool/1.0"
        """)
    client.save({"conanfile.py": consumer}, clean_first=True)
    client.run("install . -pr:b=default")
    toolchain = client.load("conan_toolchain.cmake")
    assert 'include("mytoolchain.cmake")' in toolchain

    consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeToolchain

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            build_requires = "mytool/1.0"

            def generate(self):
                CMakeToolchain(self).generate()
        """)
    client.save({"conanfile.py": consumer}, clean_first=True)
    client.run("install . -pr:b=default")
    toolchain = client.load("conan_toolchain.cmake")
    assert 'include("mytoolchain.cmake")' in toolchain


def test_propagate_conf_info():
    """ test we can use the conf_info to propagate information from the dependencies
    to the consumers. The propagation is explicit.
    TO DISCUSS: Should conf be aggregated always from all requires?
    TODO: Backport to Conan 1.X so UserInfo is not longer necessary in 1.X
    """
    # https://github.com/conan-io/conan/issues/9571
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def package_info(self):
                self.conf_info.define("user:myinfo1", "val1")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=dep1 --version=1.0")
    client.run("create . --name=dep2 --version=1.0")

    consumer = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            requires = "dep1/1.0", "dep2/1.0"
            def generate(self):
                c1 = self.dependencies["dep1"].conf_info.get("user:myinfo1")
                c2 = self.dependencies["dep2"].conf_info.get("user:myinfo1")
                self.output.info("CONF1: {}".format(c1))
                self.output.info("CONF2: {}".format(c2))
        """)
    client.save({"conanfile.py": consumer}, clean_first=True)
    client.run("install . ")
    assert "conanfile.py: CONF1: val1" in client.out
    assert "conanfile.py: CONF2: val1" in client.out


def test_conf_transitive_tool():
    """
    # https://github.com/conan-io/conan/issues/14421
    app --(tool_requires)--> tool/0.1 -> lib/0.1 -(tool_require)-> libbuilder/0.1 -> zlib/0.1

    profile-host = Debug
    profile-build = Release
    """

    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            version = "0.1"
            settings = "build_type"
            {}
            def package_info(self):
                self.output.info(f"host: {{self.settings.build_type}}")
                self.output.info(f"build: {{self.settings_build.build_type}}")
                if self.settings_target is not None:
                    self.output.info(f"target: {{self.settings_target.build_type}}")
        """)
    client.save({"zlib/conanfile.py": conanfile.format(""),
                 "libbuilder/conanfile.py": conanfile.format("requires='zlib/0.1'"),
                 "lib/conanfile.py": conanfile.format("tool_requires='libbuilder/0.1'"),
                 "tool/conanfile.py": conanfile.format("requires='lib/0.1'"),
                 "app/conanfile.py": conanfile.format("tool_requires='tool/0.1'")})
    client.run("export zlib --name=zlib")
    client.run("export libbuilder --name=libbuilder")
    client.run("export lib --name=lib")
    client.run("export tool --name=tool")
    client.run("create app --name=app -s:b build_type=Release -s:h build_type=Debug --build=missing")
    for lib in "zlib", "libbuilder":
        assert f"{lib}/0.1: host: Release" in client.out
        assert f"{lib}/0.1: build: Release" in client.out
        assert f"{lib}/0.1: target: Release" in client.out  # used to create lib/0.1 that is Release!
    for lib in "lib", "tool":
        assert f"{lib}/0.1: host: Release" in client.out
        assert f"{lib}/0.1: build: Release" in client.out
        assert f"{lib}/0.1: target: Debug" in client.out  # used to create app/0.1 that is Debug!
    assert "app/0.1: host: Debug" in client.out
    assert "app/0.1: build: Release" in client.out


def test_conf_both_build_and_host():
    """
    # https://github.com/conan-io/conan/issues/14421
    app --(requires)-----> protobuf(lib-host-release) -(tool_require)-> tool/0.1
      \\- (tool_require)-> protobuf(protoc-build-release) -(tool_require) -> tool/0.1

    profile-host = Debug
    profile-build = Release
    """

    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "tool"
            version = "0.1"
            def package_info(self):
                myvalue = str(self.settings_target.build_type)
                self.conf_info.define("user.team:myconf", myvalue)
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --build-require")

    myprotobuf = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "myprotobuf"
            version = "0.1"
            settings = "build_type"
            tool_requires = "tool/0.1"

            def generate(self):
                self.output.info(f"MYCONF {self.context}: {self.conf.get('user.team:myconf')}")
        """)

    client.save({"myprotobuf/conanfile.py": myprotobuf,
                 "app/conanfile.py": GenConanfile().with_requires("myprotobuf/0.1")
                                                   .with_tool_requires("myprotobuf/0.1")},
                clean_first=True)
    client.run('export myprotobuf')
    client.run("install app --build=missing -s:h build_type=Debug -s:b build_type=Release")
    assert "myprotobuf/0.1: MYCONF build: Release" in client.out
    assert "myprotobuf/0.1: MYCONF host: Debug" in client.out
