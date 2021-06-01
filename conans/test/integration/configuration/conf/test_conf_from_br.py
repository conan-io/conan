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
    client.run("install .")
    assert "conanfile.py: NDK: MY-NDK!!!" in client.out

    client.run("install . -pr=android")
    assert "conanfile.py: NDK: MY-SYSTEM-NDK!!!" in client.out
