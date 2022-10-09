import os
import textwrap
import unittest

import pytest

from conans.test.utils.tools import TestClient
from conans.util.files import mkdir


class RemoveSubsettingTest(unittest.TestCase):

    def test_remove_options(self):
        # https://github.com/conan-io/conan/issues/2327
        # https://github.com/conan-io/conan/issues/2781
        client = TestClient()
        conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    options = {"opt1": [True, False], "opt2": [True, False]}
    default_options = {"opt1": True, "opt2": False}
    def config_options(self):
        del self.options.opt2
    def build(self):
        assert "opt2" not in self.options
        self.options.opt2
"""
        client.save({"conanfile.py": conanfile})
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        client.current_folder = build_folder
        client.run("install ..")
        client.run("build ..", assert_error=True)
        self.assertIn("ConanException: option 'opt2' doesn't exist", client.out)
        self.assertIn("Possible options are ['opt1']", client.out)

    def test_remove_setting(self):
        # https://github.com/conan-io/conan/issues/2327
        client = TestClient()
        conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    settings = "os", "build_type"
    def configure(self):
        del self.settings.build_type

    def build(self):
        self.settings.build_type
"""
        client.save({"conanfile.py": conanfile})
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        client.current_folder = build_folder

        client.run("build ..", assert_error=True)
        self.assertIn("'settings.build_type' doesn't exist", client.out)

    @pytest.mark.xfail(reason="Move this to CMakeToolchain")
    def test_remove_subsetting(self):
        # https://github.com/conan-io/conan/issues/2049
        client = TestClient()
        base = '''from conan import ConanFile
class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
'''
        test = """from conan import ConanFile, CMake
class ConanLib(ConanFile):
    settings = "compiler", "arch"

    def configure(self):
        del self.settings.compiler.libcxx

    def test(self):
        pass

    def build(self):
        cmake = CMake(self)
        self.output.info("TEST " + cmake.command_line)
"""
        client.save({"conanfile.py": base,
                     "test_package/conanfile.py": test})
        client.run("create . --user=user --channel=testing -s arch=x86_64 -s compiler=gcc "
                   "-s compiler.version=4.9 -s compiler.libcxx=libstdc++11")
        self.assertNotIn("LIBCXX", client.out)

    @pytest.mark.xfail(reason="Move this to CMakeToolchain")
    def test_remove_subsetting_build(self):
        # https://github.com/conan-io/conan/issues/2049
        client = TestClient()

        conanfile = """from conan import ConanFile, CMake
class ConanLib(ConanFile):
    settings = "compiler", "arch"

    def package(self):
        try:
            self.settings.compiler.libcxx
        except Exception as e:
            self.output.error("PACKAGE " + str(e))

    def configure(self):
        del self.settings.compiler.libcxx

    def build(self):
        try:
            self.settings.compiler.libcxx
        except Exception as e:
            self.output.error("BUILD " + str(e))
        cmake = CMake(self)
        self.output.info("BUILD " + cmake.command_line)
"""
        client.save({"conanfile.py": conanfile})
        client.run("build . -s arch=x86_64 -s compiler=gcc -s compiler.version=4.9 "
                   "-s compiler.libcxx=libstdc++11")
        self.assertIn("ERROR: BUILD 'settings.compiler.libcxx' doesn't exist for 'gcc'",
                      client.out)
        self.assertNotIn("LIBCXX", client.out)


def test_settings_and_options_rm_safe():
    client = TestClient()
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    class Pkg(ConanFile):
        settings = "os", "build_type", "compiler"
        options = {"opt1": [True, False], "opt2": [True, False]}
        default_options = {"opt1": "True", "opt2": "False"}

        def configure(self):
            # setting
            self.settings.rm_safe("build_type")
            # sub-setting
            self.settings.rm_safe("compiler.version")
            # wrong settings
            self.settings.rm_safe("fake_field")
            self.settings.rm_safe("fake_field.version")

        def config_options(self):
            # option
            self.options.rm_safe("opt2")
            # wrong option
            self.options.rm_safe("opt15")

        def build(self):
            try:
                self.settings.build_type
            except Exception as exc:
                self.output.warning(str(exc))
            try:
                self.settings.compiler.version
            except Exception as exc:
                self.output.warning(str(exc))
            try:
                self.options.opt2
            except Exception as exc:
                self.output.warning(str(exc))
            assert "opt2" not in self.options
    """)
    client.save({"conanfile.py": conanfile})
    client.run("install .")
    client.run("build .")
    assert "'settings.build_type' doesn't exist" in client.out
    assert "'settings' possible configurations are ['compiler', 'os']" in client.out
    assert "'settings.compiler.version' doesn't exist" in client.out
    assert "'settings.compiler' possible configurations are [" in client.out
    assert "option 'opt2' doesn't exist" in client.out
    assert "Possible options are ['opt1']" in client.out
