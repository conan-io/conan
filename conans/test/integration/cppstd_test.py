import unittest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient


class StdCppTest(unittest.TestCase):

    def use_wrong_setting_for_compiler_test(self):
        client = TestClient()

        conanfile = """from conans import ConanFile

class TestConan(ConanFile):
    name = "MyLib"
    version = "0.1"
    settings = "compiler", "cppstd"

"""
        client.save({CONANFILE: conanfile})
        error = client.run('create . user/testing -s compiler="gcc" '
                           '-s compiler.libcxx="libstdc++11" '
                           '-s compiler.version="4.6" -s cppstd=17', ignore_error=True)
        self.assertTrue(error)
        self.assertIn("The specified 'cppstd=17' is not available for 'gcc 4.6'", client.out)
        self.assertIn("Possible values are ['98', 'gnu98', '11', 'gnu11']", client.out)

        client.run('create . user/testing -s compiler="gcc" -s compiler.libcxx="libstdc++11" '
                   '-s compiler.version="6.3" -s cppstd=17')

    def set_default_package_id_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile

class TestConan(ConanFile):
    name = "MyLib"
    version = "0.1"
    settings = "compiler", %s

    def build(self):
        self.output.warn("BUILDING!")
"""
        client.save({CONANFILE: conanfile % ""})  # Without the setting
        client.run('create . user/testing -s compiler="gcc" -s compiler.version="7.1" '
                   '-s compiler.libcxx="libstdc++" '
                   '--build missing')
        self.assertIn("BUILDING!", client.out)

        # Add the setting but with the default value, should not build again
        client.save({CONANFILE: conanfile % '"cppstd"'})  # With the setting
        client.run('create . user/testing -s compiler="gcc" -s compiler.version="7.1" '
                   '-s compiler.libcxx="libstdc++" '
                   '-s cppstd=gnu14 '
                   '--build missing')
        self.assertNotIn("BUILDING!", client.out)

        # Add the setting but with a non-default value, should build again
        client.save({CONANFILE: conanfile % '"cppstd"'})  # With the setting
        client.run('create . user/testing -s compiler="gcc" -s compiler.version="7.1" '
                   '-s compiler.libcxx="libstdc++" '
                   '-s cppstd=gnu17 '
                   '--build missing')
        self.assertIn("BUILDING!", client.out)
