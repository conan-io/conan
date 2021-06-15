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
