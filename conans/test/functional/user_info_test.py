import os
import unittest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient
from conans.util.files import load


class UserInfoTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def test_user_info_propagation(self):

        def export_lib(name, requires, infolines):
            base = '''
import os
from conans import ConanFile

class MyConanfile(ConanFile):
    name = "%s"
    version = "0.1"
    requires = "%s"

    def build(self):
        pass

    def package_info(self):
        %s
    '''
            self.client.save({CONANFILE: base % (name, requires, infolines)}, clean_first=True)
            self.client.run("export lasote/stable")

        export_lib("LIB_A", "", "self.user_info.VAR1=2")
        export_lib("LIB_B", "LIB_A/0.1@lasote/stable", "self.user_info.VAR1=2\n        "
                                                       "self.user_info.VAR2=3")
        export_lib("LIB_C", "LIB_B/0.1@lasote/stable", "self.user_info.VAR1=2")
        export_lib("LIB_D", "LIB_C/0.1@lasote/stable", "self.user_info.var1=2")

        reuse = '''
import os
from conans import ConanFile

class MyConanfile(ConanFile):
    name = "reuse"
    version = "0.1"
    requires = "LIB_D/0.1@lasote/stable"

    def build(self):
        assert(self.deps_user_info["LIB_A"].VAR1=="2")
        assert(self.deps_user_info["LIB_B"].VAR1=="2")
        assert(self.deps_user_info["LIB_B"].VAR2=="3")
        assert(self.deps_user_info["LIB_C"].VAR1=="2")
        assert(self.deps_user_info["LIB_D"].var1=="2")
    '''
        self.client.save({CONANFILE: reuse}, clean_first=True)
        self.client.run("export lasote/stable")
        self.client.run('install reuse/0.1@lasote/stable --build -g txt')

        # Assert generator TXT
        txt_contents = load(os.path.join(self.client.current_folder, "conanbuildinfo.txt"))
        self.assertIn("[USER_LIB_A:VAR1]%s2" % os.linesep, txt_contents)
        self.assertIn("[USER_LIB_B:VAR1]%s2" % os.linesep, txt_contents)
        self.assertIn("[USER_LIB_B:VAR2]%s3" % os.linesep, txt_contents)
        self.assertIn("[USER_LIB_C:VAR1]%s2" % os.linesep, txt_contents)
        self.assertIn("[USER_LIB_D:var1]%s2" % os.linesep, txt_contents)

        # Now try local command with a consumer
        self.client.run('install . --build -g txt')
        self.client.run("build")

