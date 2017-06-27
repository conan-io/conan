import unittest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient
from conans.util.files import save


class DefaultProfileTest(unittest.TestCase):

    def test_profile_applied_ok(self):
        client = TestClient()

        default_profile = """
[settings]
os=Windows
compiler=Visual Studio
compiler.version=14
compiler.runtime=MD
arch=x86

[env]
MyVAR=23

[options]
mypackage:option1=2

[build_requires]
br/1.0@lasote/stable
"""
        save(client.client_cache.default_profile_path, default_profile)
        br = '''
from conans import ConanFile

class BuildRequireConanfile(ConanFile):
    name = "br"
    version = "0.1"
    settings = "os", "compiler", "arch"

    def package_info(self):
        self.env_info.MYVAR="from_build_require"

'''
        client.save({CONANFILE: br})
        client.run("export lasote/stable")

        cf = '''
import os
from conans import ConanFile

class MyConanfile(ConanFile):
    name = "mypackage"
    version = "0.1"
    settings = "os", "compiler", "arch"
    options = {"option1": ["1", "2"]}
    default_options = "option1=1"

    def configure(self):
        assert(self.settings.os=="Windows")
        assert(self.settings.compiler=="Visual Studio")
        assert(self.settings.compiler.version=="14")
        assert(self.settings.compiler.runtime=="MD")
        assert(self.settings.arch=="x86")
        assert(self.options.option1=="2")
        assert(os.environ["MyVAR"], "from_build_require")

        '''
        client.save({CONANFILE: cf}, clean_first=True)
        client.run("export lasote/stable")
        client.run('install mypackage/0.1@lasote/stable --build missing')
