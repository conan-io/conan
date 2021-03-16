import os
import textwrap
import unittest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient


class UserInfoTest(unittest.TestCase):

    def test_user_info_propagation(self):
        client = TestClient()

        def export_lib(name, requires, infolines):
            base = textwrap.dedent("""
                from conans import ConanFile

                class MyConanfile(ConanFile):
                    name = "%s"
                    version = "0.1"
                    requires = "%s"

                    def package_info(self):
                        %s
                    """)
            client.save({CONANFILE: base % (name, requires, infolines)}, clean_first=True)
            client.run("export . lasote/stable")

        export_lib("LIB_A", "", "self.user_info.VAR1=2")
        export_lib("LIB_B", "LIB_A/0.1@lasote/stable", "self.user_info.VAR1=2\n        "
                                                       "self.user_info.VAR2=3")
        export_lib("LIB_C", "LIB_B/0.1@lasote/stable", "self.user_info.VAR1=2")
        export_lib("LIB_D", "LIB_C/0.1@lasote/stable", "self.user_info.var1=2")

        reuse = textwrap.dedent("""
            from conans import ConanFile

            class MyConanfile(ConanFile):
                requires = "LIB_D/0.1@lasote/stable"

                def build(self):
                    assert(self.deps_user_info["LIB_A"].VAR1=="2")
                    assert(self.deps_user_info["LIB_B"].VAR1=="2")
                    assert(self.deps_user_info["LIB_B"].VAR2=="3")
                    assert(self.deps_user_info["LIB_C"].VAR1=="2")
                    assert(self.deps_user_info["LIB_D"].var1=="2")
                    # Idiomatic way to check for attribute existence
                    # https://github.com/conan-io/conan/issues/7130
                    assert(hasattr(self.deps_user_info["LIB_A"], "VAR1"))
                    assert(not hasattr(self.deps_user_info["LIB_A"], "NONEXIST"))
                    assert(getattr(self.deps_user_info["LIB_A"], "VAR1"))
                    assert(not getattr(self.deps_user_info["LIB_A"], "NONEXIST", None))
                """)
        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("export . reuse/0.1@lasote/stable")
        client.run('install reuse/0.1@lasote/stable --build -g txt')

        # Assert generator TXT
        txt_contents = client.load("conanbuildinfo.txt")
        self.assertIn("[USER_LIB_A]%sVAR1=2" % os.linesep, txt_contents)
        self.assertIn("[USER_LIB_B]%sVAR1=2%sVAR2=3" % (os.linesep, os.linesep), txt_contents)
        self.assertIn("[USER_LIB_C]%sVAR1=2" % os.linesep, txt_contents)
        self.assertIn("[USER_LIB_D]%svar1=2" % os.linesep, txt_contents)

        # Now try local command with a consumer
        client.run('install . --build')
        client.run("build .")
