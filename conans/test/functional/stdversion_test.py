import unittest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient


class StdCppTest(unittest.TestCase):

    def use_wrong_option_for_compiler_test(self):
        client = TestClient()

        conanfile = """from conans import ConanFile

class TestConan(ConanFile):
    name = "MyLib"
    version = "0.1"
    settings = "compiler"
    def options(self, config):
        config.add_cppstd()
"""
        client.save({CONANFILE: conanfile})
        error = client.run('create user/testing -s compiler="gcc" -s compiler.libcxx="libstdc++11" '
                           '-s compiler.version="4.6" -o MyLib:cppstd=17', ignore_error=True)
        self.assertTrue(error)
        self.assertIn("MyLib/0.1@user/testing: '17' is not a valid 'options.cppstd' value.",
                      client.out)
        self.assertIn("Possible values are ['11', '11gnu', '98', '98gnu', 'None']", client.out)

        client.run('create user/testing -s compiler="gcc" -s compiler.libcxx="libstdc++11" '
                   '-s compiler.version="6.3" -o MyLib:cppstd=17')

    def set_default_value_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile

class TestConan(ConanFile):
    name = "MyLib"
    version = "0.1"
    settings = "compiler",

    @staticmethod
    def options(config):
        config.add_cppstd(default="11" if config.settings.compiler != "Visual Studio" else None)

    def build(self):
        self.output.warn("STD=%s" % self.options.cppstd)
"""
        client.save({CONANFILE: conanfile})
        error = client.run('create user/testing -s compiler="gcc" -s compiler.libcxx="libstdc++11" '
                           '-s compiler.version="4.1"', ignore_error=True)
        self.assertTrue(error)
        self.assertIn("11' is not a valid 'options.cppstd' value", client.out)
        client.run('create user/testing -s compiler="Visual Studio" -s compiler.version="15"')
        self.assertIn("WARN: STD=None", client.out)

        client.run('create user/testing -s compiler="gcc" -s compiler.libcxx="libstdc++11" '
                   '-s compiler.version="7.1"')
        self.assertIn("WARN: STD=11", client.out)
