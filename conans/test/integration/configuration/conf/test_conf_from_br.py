import textwrap

from conans.test.utils.tools import TestClient


def test_basic():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):

            def package_info(self):
                self.conf_info["tools.android:ndk_path"] = "MY-NDK!!!"
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
                self.conf_info.append("tools.cmake.cmaketoolchain:user_toolchain", "mytoolchain.cmake")
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
