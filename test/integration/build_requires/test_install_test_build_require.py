import json
import platform
import textwrap

import pytest

from conan.tools.env.environment import environment_wrap_command
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def client():
    openssl = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            settings = "os"
            package_type = "shared-library"
            def package(self):
                with chdir(self, self.package_folder):
                    echo = "@echo off\necho MYOPENSSL={}!!".format(self.settings.os)
                    save(self, "bin/myopenssl.bat", echo)
                    save(self, "bin/myopenssl.sh", echo)
                    os.chmod("bin/myopenssl.sh", 0o777)
            """)

    cmake = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            settings = "os"
            requires = "openssl/1.0"
            def package(self):
                with chdir(self, self.package_folder):
                    echo = "@echo off\necho MYCMAKE={}!!".format(self.settings.os)
                    save(self, "mycmake.bat", echo + "\ncall myopenssl.bat")
                    save(self, "mycmake.sh", echo + "\n myopenssl.sh")
                    os.chmod("mycmake.sh", 0o777)

            def package_info(self):
                self.buildenv_info.append_path("PATH", self.package_folder)
            """)

    client = TestClient()
    client.save({"tool/conanfile.py": GenConanfile(),
                 "cmake/conanfile.py": cmake,
                 "openssl/conanfile.py": openssl})

    client.run("create tool --name=tool --version=1.0")
    client.run("create openssl --name=openssl --version=1.0")
    client.run("create cmake --name=mycmake --version=1.0")
    return client


@pytest.mark.parametrize("build_profile", ["", "-pr:b=default"])
def test_build_require_test_package(build_profile, client):
    test_cmake = textwrap.dedent(r"""
        import os, platform, sys
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os"

            def requirements(self):
                self.tool_requires(self.tested_reference_str)

            def build(self):
                mybuild_cmd = "mycmake.bat" if platform.system() == "Windows" else "mycmake.sh"
                self.run(mybuild_cmd)

            def test(self):
                pass
        """)

    # Test with extra build_requires to check it doesn't interfere or get deleted
    client.save({"cmake/test_package/conanfile.py": test_cmake})
    client.run("create cmake --name=mycmake --version=1.0 {} --build=missing".format(build_profile))

    def check(out):
        system = {"Darwin": "Macos"}.get(platform.system(), platform.system())
        assert "MYCMAKE={}!!".format(system) in out
        assert "MYOPENSSL={}!!".format(system) in out

    check(client.out)

    client.run("test cmake/test_package mycmake/1.0@ {}".format(build_profile))
    check(client.out)


def test_both_types(client):
    # When testing same package in both contexts, the 2 profiles approach must be used
    test_cmake = textwrap.dedent(r"""
        import os, platform
        from conan import ConanFile

        class Pkg(ConanFile):
            settings = "os"

            def requirements(self):
                self.requires(self.tested_reference_str)
                self.build_requires(self.tested_reference_str)

            def build(self):
                mybuild_cmd = "mycmake.bat" if platform.system() == "Windows" else "mycmake.sh"
                self.run(mybuild_cmd)

            def test(self):
                pass
        """)

    # Test with extra build_requires to check it doesn't interfere or get deleted
    client.save({"cmake/test_package/conanfile.py": test_cmake})
    # This must use the build-host contexts to have same dep in different contexts
    client.run("create cmake --name=mycmake --version=1.0 -pr:b=default --build=missing")

    def check(out):
        system = {"Darwin": "Macos"}.get(platform.system(), platform.system())
        assert "MYCMAKE={}!!".format(system) in out
        assert "MYOPENSSL={}!!".format(system) in out

    check(client.out)

    client.run("test cmake/test_package mycmake/1.0@ -pr:b=default")
    check(client.out)


def test_create_build_requires():
    # test that I can create a package passing the build and host context and package will get both
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os"

            def package_info(self):
                self.output.info("MYOS=%s!!!" % self.settings.os)
                self.output.info("MYTARGET={}!!!".format(self.settings_target.os))
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=br --version=0.1  --build-require -s:h os=Linux -s:b os=Windows")
    client.assert_listed_binary({"br/0.1": ("ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715", "Build")},
                                build=True)
    assert "br/0.1: MYOS=Windows!!!" in client.out
    assert "br/0.1: MYTARGET=Linux!!!" in client.out
    assert "br/0.1: MYOS=Linux!!!" not in client.out


def test_build_require_conanfile_text(client):
    client.save({"conanfile.txt": "[tool_requires]\nmycmake/1.0"}, clean_first=True)
    client.run("install . -g VirtualBuildEnv")
    ext = ".bat" if platform.system() == "Windows" else ".sh"
    cmd = environment_wrap_command("conanbuild", client.current_folder, f"mycmake{ext}")
    client.run_command(cmd)
    system = {"Darwin": "Macos"}.get(platform.system(), platform.system())
    assert "MYCMAKE={}!!".format(system) in client.out
    assert "MYOPENSSL={}!!".format(system) in client.out


def test_build_require_command_line_build_context(client):
    client.run("install --tool-requires=mycmake/1.0@ -g VirtualBuildEnv -pr:b=default")
    ext = ".bat" if platform.system() == "Windows" else ".sh"
    cmd = environment_wrap_command("conanbuild", client.current_folder, f"mycmake{ext}")
    client.run_command(cmd)
    system = {"Darwin": "Macos"}.get(platform.system(), platform.system())
    assert "MYCMAKE={}!!".format(system) in client.out
    assert "MYOPENSSL={}!!".format(system) in client.out


def test_install_multiple_tool_requires_cli():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile()})
    c.run("create . --name=zlib --version=1.1")
    c.run("create . --name=cmake --version=0.1")
    c.run("create . --name=gcc --version=0.2")
    c.run("install --tool-requires=cmake/0.1 --tool-requires=gcc/0.2 --requires=zlib/1.1")
    c.assert_listed_require({"cmake/0.1": "Cache", "gcc/0.2": "Cache"}, build=True)
    c.assert_listed_require({"zlib/1.1": "Cache"})


def test_bootstrap_other_architecture():
    """ this is the case of libraries as ICU, that needs itself for cross-compiling
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.build import cross_building

        class Pkg(ConanFile):
            name = "tool"
            version = "1.0"
            settings = "os"
            def build_requirements(self):
                if cross_building(self):
                    self.tool_requires("tool/1.0")
        """)
    c.save({"conanfile.py": conanfile})
    win_pkg_id = "ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715"
    linux_pkg_id = "9a4eb3c8701508aa9458b1a73d0633783ecc2270"

    c.run("create . -s:b os=Windows -s:h os=Windows")
    c.assert_listed_binary({"tool/1.0": (win_pkg_id, "Build")})
    assert "Build requirements" not in c.out

    # This is smart and knows how to build only the missing one "host" but not "build"
    c.run("create . -s:b os=Windows -s:h os=Linux --build=missing:tool*")
    c.assert_listed_binary({"tool/1.0": (linux_pkg_id, "Build")})
    c.assert_listed_binary({"tool/1.0": (win_pkg_id, "Cache")}, build=True)

    # This will rebuild all
    c.run("create . -s:b os=Windows -s:h os=Linux")
    c.assert_listed_binary({"tool/1.0": (linux_pkg_id, "Build")})
    c.assert_listed_binary({"tool/1.0": (win_pkg_id, "Build")}, build=True)

    c.run("graph build-order --requires=tool/1.0 -s:b os=Windows -s:h os=Linux --build=* "
          "--format=json", redirect_stdout="o.json")
    order = json.loads(c.load("o.json"))
    package1 = order[0][0]["packages"][0][0]
    package2 = order[0][0]["packages"][1][0]
    assert package1["package_id"] == win_pkg_id
    assert package1["depends"] == []
    assert package2["package_id"] == linux_pkg_id
    assert package2["depends"] == [win_pkg_id]
