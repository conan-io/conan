import textwrap

from conans.test.utils.tools import TestClient


def test_basic():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Pkg(ConanFile):

            def package_info(self):
                self.conf_info["tools.android:ndk_path"] = "MY-NDK!!!"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . android_ndk/1.0@")

    consumer = textwrap.dedent("""
        from conans import ConanFile

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"
            build_requires = "android_ndk/1.0"

            def generate(self):
                self.output.info("NDK: %s" % self.conf["tools.android:ndk_path"])
        """)
    android_profile = textwrap.dedent("""
        include(default)
        [conf]
        tools.android:ndk_path=MY-SYSTEM-NDK!!!
        """)
    client.save({"conanfile.py": consumer,
                 "android": android_profile}, clean_first=True)
    client.run("install . -pr:b=default")
    assert "conanfile.py: NDK: MY-NDK!!!" in client.out

    client.run("install . -pr:b=default -pr:h=android")
    assert "conanfile.py: NDK: MY-SYSTEM-NDK!!!" in client.out


def test_basic_conf_through_cli():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Pkg(ConanFile):

            def package_info(self):
                self.output.info("NDK build: %s" % self.conf["tools.android:ndk_path"])
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . android_ndk/1.0@")

    consumer = textwrap.dedent("""
        from conans import ConanFile

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"
            build_requires = "android_ndk/1.0"

            def generate(self):
                self.output.info("NDK host: %s" % self.conf["tools.android:ndk_path"])
        """)
    client.save({"conanfile.py": consumer}, clean_first=True)
    client.run('install . -c:b=tools.android:ndk_path="MY-NDK!!!" '
               '-c:h=tools.android:ndk_path="MY-SYSTEM-NDK!!!"')
    assert "android_ndk/1.0: NDK build: MY-NDK!!!" in client.out
    assert "conanfile.py: NDK host: MY-SYSTEM-NDK!!!" in client.out


def test_declared_generators_get_conf():
    # https://github.com/conan-io/conan/issues/9571
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            def package_info(self):
                self.conf_info.append("tools.cmake.cmaketoolchain:user_toolchain", "mytoolchain.cmake")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . mytool/1.0@")

    consumer = textwrap.dedent("""
        from conans import ConanFile

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
        from conans import ConanFile
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
