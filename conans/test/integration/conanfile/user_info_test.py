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
                from conan import ConanFile

                class MyConanfile(ConanFile):
                    name = "%s"
                    version = "0.1"
                    requires = %s

                    def package_info(self):
                        %s
                    """)
            requires = "'{}'".format(requires) if requires else "None"
            client.save({CONANFILE: base % (name, requires, infolines)}, clean_first=True)
            client.run("export . --user=lasote --channel=stable")

        export_lib("lib_a", "", "self.user_info.VAR1=2")
        export_lib("lib_b", "lib_a/0.1@lasote/stable", "self.user_info.VAR1=2\n        "
                                                       "self.user_info.VAR2=3")
        export_lib("lib_c", "lib_b/0.1@lasote/stable", "self.user_info.VAR1=2")
        export_lib("lib_d", "lib_c/0.1@lasote/stable", "self.user_info.var1=2")

        reuse = textwrap.dedent("""
            from conan import ConanFile

            class MyConanfile(ConanFile):
                requires = "lib_d/0.1@lasote/stable"

                def build(self):
                    assert self.dependencies["lib_a"].user_info.VAR1=="2"
                    assert self.dependencies["lib_b"].user_info.VAR1=="2"
                    assert self.dependencies["lib_b"].user_info.VAR2=="3"
                    assert self.dependencies["lib_c"].user_info.VAR1=="2"
                    assert self.dependencies["lib_c"].user_info.VAR1=="2"
                """)
        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("export . --name=reuse --version=0.1 --user=lasote --channel=stable")
        client.run('install --reference=reuse/0.1@lasote/stable --build=*')
        # Now try local command with a consumer
        client.run('install . --build=*')
        client.run("build .")
