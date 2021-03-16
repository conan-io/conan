import os
import textwrap
import unittest

from parameterized import parameterized

from conans.test.utils.tools import TestClient
from conans.util.files import mkdir


class SetVersionNameTest(unittest.TestCase):

    @parameterized.expand([("", ), ("@user/channel", )])
    def test_set_version_name(self, user_channel):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Lib(ConanFile):
                def set_name(self):
                    self.name = "pkg"
                def set_version(self):
                    self.version = "2.1"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . %s" % user_channel)
        self.assertIn("pkg/2.1%s: A new conanfile.py version was exported" % user_channel,
                      client.out)
        # installing it doesn't break
        client.run("install pkg/2.1%s --build=missing" % (user_channel or "@"))
        self.assertIn("pkg/2.1%s:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build" % user_channel,
                      client.out)
        client.run("install pkg/2.1%s --build=missing" % (user_channel or "@"))
        self.assertIn("pkg/2.1%s:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache" % user_channel,
                      client.out)

        # Local flow should also work
        client.run("install .")
        self.assertIn("conanfile.py (pkg/2.1): Installing package", client.out)

    def test_set_version_name_file(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, load
            class Lib(ConanFile):
                def set_name(self):
                    self.name = load("name.txt")
                def set_version(self):
                    self.version = load("version.txt")
            """)
        client.save({"conanfile.py": conanfile,
                     "name.txt": "pkg",
                     "version.txt": "2.1"})
        client.run("export . user/testing")
        self.assertIn("pkg/2.1@user/testing: A new conanfile.py version was exported", client.out)
        client.run("install pkg/2.1@user/testing --build=missing")
        self.assertIn("pkg/2.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build",
                      client.out)
        client.run("install pkg/2.1@user/testing")
        self.assertIn("pkg/2.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache",
                      client.out)
        # Local flow should also work
        client.run("install .")
        self.assertIn("conanfile.py (pkg/2.1): Installing package", client.out)

    def test_set_version_name_errors(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Lib(ConanFile):
                def set_name(self):
                    self.name = "pkg"
                def set_version(self):
                    self.version = "2.1"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . other/1.1@user/testing", assert_error=True)
        self.assertIn("ERROR: Package recipe with name other!=pkg", client.out)
        client.run("export . 1.1@user/testing", assert_error=True)
        self.assertIn("ERROR: Package recipe with version 1.1!=2.1", client.out)
        # These are checked but match and don't conflict
        client.run("export . 2.1@user/testing")
        client.run("export . pkg/2.1@user/testing")

        # Local flow should also fail
        client.run("install . other/1.2@", assert_error=True)
        self.assertIn("ERROR: Package recipe with name other!=pkg", client.out)

    def test_set_version_name_only_not_cli(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Lib(ConanFile):
                def set_name(self):
                    self.name = self.name or "pkg"
                def set_version(self):
                    self.version = self.version or "2.0"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export . other/1.1@user/testing")
        self.assertIn("other/1.1@user/testing: Exported", client.out)
        client.run("export . 1.1@user/testing")
        self.assertIn("pkg/1.1@user/testing: Exported", client.out)
        client.run("export . user/testing")
        self.assertIn("pkg/2.0@user/testing: Exported", client.out)

        # Local flow should also work
        client.run("install . other/1.2@")
        self.assertIn("conanfile.py (other/1.2)", client.out)
        client.run("install .")
        self.assertIn("conanfile.py (pkg/2.0)", client.out)

    def test_set_version_name_crash(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Lib(ConanFile):
                def set_name(self):
                    self.name = error
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export .", assert_error=True)
        self.assertIn("ERROR: conanfile.py: Error in set_name() method, line 5", client.out)
        self.assertIn("name 'error' is not defined", client.out)
        conanfile = textwrap.dedent("""
           from conans import ConanFile
           class Lib(ConanFile):
               def set_version(self):
                   self.version = error
           """)
        client.save({"conanfile.py": conanfile})
        client.run("export .", assert_error=True)
        self.assertIn("ERROR: conanfile.py: Error in set_version() method, line 5", client.out)
        self.assertIn("name 'error' is not defined", client.out)

    def test_set_version_recipe_folder(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, load
            class Lib(ConanFile):
                name = "pkg"
                def set_version(self):
                    self.version = load(os.path.join(self.recipe_folder, "version.txt"))
            """)
        client.save({"conanfile.py": conanfile,
                     "version.txt": "2.1"})
        mkdir(os.path.join(client.current_folder, "build"))
        with client.chdir("build"):
            client.run("export .. user/testing")
            self.assertIn("pkg/2.1@user/testing: A new conanfile.py version was exported",
                          client.out)

        # This is reusable with python_requires too
        reuse = textwrap.dedent("""
            from conans import python_requires
            tool = python_requires("pkg/2.1@user/testing")
            class Consumer(tool.Lib):
                name = "consumer"
            """)
        client2 = TestClient(cache_folder=client.cache_folder)
        client2.save({"conanfile.py": reuse,
                      "version.txt": "8.3"})
        client2.run("export .")
        self.assertIn("consumer/8.3: A new conanfile.py version was exported", client2.out)

    def test_set_version_cwd(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, load
            class Lib(ConanFile):
                name = "pkg"
                def set_version(self):
                    self.version = load("version.txt")
            """)
        client.save({"conanfile.py": conanfile})
        mkdir(os.path.join(client.current_folder, "build"))
        with client.chdir("build"):
            client.save({"version.txt": "2.1"}, clean_first=True)
            client.run("export .. ")
            self.assertIn("pkg/2.1: A new conanfile.py version was exported", client.out)
