import unittest

import os

from conans.paths import CONANFILE
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import save


class DefaultProfileTest(unittest.TestCase):

    def conanfile_txt_incomplete_profile_test(self):
        conanfile = '''from conans import ConanFile
class MyConanfile(ConanFile):
    pass
'''

        client = TestClient()
        save(client.client_cache.default_profile_path, "[env]\nValue1=A")

        client.save({CONANFILE: conanfile})
        client.run("create . Pkg/0.1@lasote/stable")
        self.assertIn("Pkg/0.1@lasote/stable: Package '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9' "
                      "created", client.out)

        client.save({"conanfile.txt": "[requires]\nPkg/0.1@lasote/stable"}, clean_first=True)
        client.run('install .')
        self.assertIn("Pkg/0.1@lasote/stable: Already installed!", client.out)

    def change_default_profile_test(self):
        br = '''
import os
from conans import ConanFile

class MyConanfile(ConanFile):
    name = "mylib"
    version = "0.1"

    def build(self):
        assert(os.environ.get("Value1") == "A")

'''
        tmp = temp_folder()
        default_profile_path = os.path.join(tmp, "myprofile")
        save(default_profile_path, "[env]\nValue1=A")
        client = TestClient()
        client.run("config set general.default_profile='%s'" % default_profile_path)
        client.save({CONANFILE: br})
        client.run("export . lasote/stable")
        client.run('install mylib/0.1@lasote/stable --build')

        # Now use a name, in the default profile folder
        os.unlink(default_profile_path)
        save(os.path.join(client.client_cache.profiles_path, "other"), "[env]\nValue1=A")
        client.run("config set general.default_profile=other")
        client.save({CONANFILE: br})
        client.run("export . lasote/stable")
        client.run('install mylib/0.1@lasote/stable --build')

    def test_profile_applied_ok(self):
        br = '''
import os
from conans import ConanFile

class BuildRequireConanfile(ConanFile):
    name = "br"
    version = "1.0"
    settings = "os", "compiler", "arch"

    def package_info(self):
        self.env_info.MyVAR="from_build_require"
'''

        client = TestClient()

        default_profile = """
[settings]
os=Windows
compiler=Visual Studio
compiler.version=14
compiler.runtime=MD
arch=x86

[options]
mypackage:option1=2

[build_requires]
br/1.0@lasote/stable
"""
        save(client.client_cache.default_profile_path, default_profile)

        client.save({CONANFILE: br})
        client.run("export . lasote/stable")

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
    
    def build(self):
        # This has changed, the value from profile higher priority than build require
        assert(os.environ["MyVAR"]=="%s")

        '''

        # First apply just the default profile, we should get the env MYVAR="from_build_require"
        client.save({CONANFILE: cf % "from_build_require"}, clean_first=True)
        client.run("export . lasote/stable")
        client.run('install mypackage/0.1@lasote/stable --build missing')

        # Then declare in the default profile the var, it should be prioritized from the br
        default_profile_2 = default_profile + "\n[env]\nMyVAR=23"
        save(client.client_cache.default_profile_path, default_profile_2)
        client.save({CONANFILE: cf % "23"}, clean_first=True)
        client.run("export . lasote/stable")
        client.run('install mypackage/0.1@lasote/stable --build missing')
