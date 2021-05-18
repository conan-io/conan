import platform
import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def client():
    openssl = textwrap.dedent(r"""
        import os
        from conans import ConanFile
        from conans.tools import save, chdir
        class Pkg(ConanFile):
            settings = "os"
            def package(self):
                with chdir(self.package_folder):
                    echo = "@echo off\necho MYOPENSSL={}!!".format(self.settings.os)
                    save("bin/myopenssl.bat", echo)
                    save("bin/myopenssl.sh", echo)
                    os.chmod("bin/myopenssl.sh", 0o777)

            def package_info(self):
                self.env_info.PATH = [os.path.join(self.package_folder, "bin")]
            """)

    cmake = textwrap.dedent(r"""
        import os
        from conans import ConanFile
        from conans.tools import save, chdir
        class Pkg(ConanFile):
            settings = "os"
            requires = "openssl/1.0"
            def package(self):
                with chdir(self.package_folder):
                    echo = "@echo off\necho MYCMAKE={}!!".format(self.settings.os)
                    save("mycmake.bat", echo + "\ncall myopenssl.bat")
                    save("mycmake.sh", echo + "\n myopenssl.sh")
                    os.chmod("mycmake.sh", 0o777)

            def package_info(self):
                self.env_info.PATH = [self.package_folder]
            """)

    client = TestClient()
    client.save({"tool/conanfile.py": GenConanfile(),
                 "cmake/conanfile.py": cmake,
                 "openssl/conanfile.py": openssl})

    client.run("create tool tool/1.0@")
    client.run("create openssl openssl/1.0@")
    client.run("create cmake mycmake/1.0@")
    return client


@pytest.mark.parametrize("existing_br", ["",
                                         'build_requires="tool/1.0"',
                                         'build_requires=("tool/1.0", )',
                                         'build_requires=["tool/1.0"]'])
@pytest.mark.parametrize("build_profile", ["", "-pr:b=default"])
def test_build_require_test_package(existing_br, build_profile, client):
    test_cmake = textwrap.dedent(r"""
        import os, platform
        from conans import ConanFile
        from conans.tools import save, chdir
        class Pkg(ConanFile):
            settings = "os"
            test_type = "build_requires"
            {}

            def build(self):
                mybuild_cmd = "mycmake.bat" if platform.system() == "Windows" else "mycmake.sh"
                self.run(mybuild_cmd)

            def test(self):
                pass
        """)

    # Test with extra build_requires to check it doesn't interfere or get deleted
    client.save({"cmake/test_package/conanfile.py": test_cmake.format(existing_br)})
    client.run("create cmake mycmake/1.0@ {} --build=missing".format(build_profile))

    def check(out):
        if "tool" in existing_br:
            assert "mycmake/1.0 (test package): Applying build-requirement: tool/1.0" in out
        else:
            assert "tool/1.0" not in out

        assert "mycmake/1.0 (test package): Applying build-requirement: openssl/1.0" in out
        assert "mycmake/1.0 (test package): Applying build-requirement: mycmake/1.0" in out

        system = {"Darwin": "Macos"}.get(platform.system(), platform.system())
        assert "MYCMAKE={}!!".format(system) in out
        assert "MYOPENSSL={}!!".format(system) in out

    check(client.out)

    client.run("test cmake/test_package mycmake/1.0@ {}".format(build_profile))
    check(client.out)


@pytest.mark.parametrize("existing_br", ["",
                                         'build_requires="tool/1.0"',
                                         'build_requires=("tool/1.0", )',
                                         'build_requires=["tool/1.0"]'])
def test_both_types(existing_br, client):
    # When testing same package in both contexts, the 2 profiles approach must be used
    test_cmake = textwrap.dedent(r"""
        import os, platform
        from conans import ConanFile
        from conans.tools import save, chdir
        class Pkg(ConanFile):
            settings = "os"
            test_type = "build_requires", "requires"
            {}

            def build(self):
                mybuild_cmd = "mycmake.bat" if platform.system() == "Windows" else "mycmake.sh"
                self.run(mybuild_cmd)

            def test(self):
                pass
        """)

    # Test with extra build_requires to check it doesn't interfere or get deleted
    client.save({"cmake/test_package/conanfile.py": test_cmake.format(existing_br)})
    # This must use the build-host contexts to have same dep in different contexts
    client.run("create cmake mycmake/1.0@ -pr:b=default --build=missing")

    def check(out):
        if "tool" in existing_br:
            assert "mycmake/1.0 (test package): Applying build-requirement: tool/1.0" in out
        else:
            assert "tool/1.0" not in out

        assert "mycmake/1.0 (test package): Applying build-requirement: openssl/1.0" in out
        assert "mycmake/1.0 (test package): Applying build-requirement: mycmake/1.0" in out

        system = {"Darwin": "Macos"}.get(platform.system(), platform.system())
        assert "MYCMAKE={}!!".format(system) in out
        assert "MYOPENSSL={}!!".format(system) in out

    check(client.out)

    client.run("test cmake/test_package mycmake/1.0@ -pr:b=default")
    check(client.out)
