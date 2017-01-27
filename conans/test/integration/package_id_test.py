import unittest
from conans.test.tools import TestClient
from conans.util.files import load
from conans.paths import CONANINFO
import os


class PackageIDTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def _export(self, name, version, package_id_text=None, requires=None,
                channel=None, default_option_value="off"):
        hello_file = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "%s"
    version = "%s"
    options = {"an_option": ["on", "off"]}
    default_options = [("an_option", "%s")]
""" % (name, version, default_option_value)
        if requires:
            hello_file += "\n    requires="
            for require in requires:
                hello_file += '"%s"' % require
        if package_id_text:
            hello_file += "\n    def package_id(self):\n        %s" % package_id_text

        self.client.save({"conanfile.py": hello_file}, clean_first=True)
        self.client.run("export %s" % (channel or "lasote/stable"))

    @property
    def conaninfo(self):
        return load(os.path.join(self.client.current_folder, CONANINFO))

    def test_version_semver_schema(self):
        self._export("Hello", "1.2.0", package_id_text=None, requires=None)
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].semver()',
                     requires=["Hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install --build missing")
        self.assertIn("Hello2/2.Y.Z", self.conaninfo)

        # Now change the Hello version and build it, if we install out requires should not be
        # needed the --build needed because Hello2 don't need to be rebuilt
        self._export("Hello", "1.5.0", package_id_text=None, requires=None)
        self.client.run("install Hello/1.5.0@lasote/stable --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].semver()',
                     requires=["Hello/1.5.0@lasote/stable"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install .")
        self.assertIn("Hello2/2.Y.Z", self.conaninfo)

        # Try to change user and channel too, should be the same, not rebuilt needed
        self._export("Hello", "1.5.0", package_id_text=None, requires=None, channel="memsharded/testing")
        self.client.run("install Hello/1.5.0@memsharded/testing --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].semver()',
                     requires=["Hello/1.5.0@memsharded/testing"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install .")
        self.assertIn("Hello2/2.Y.Z", self.conaninfo)

    def test_version_full_version_schema(self):
        self._export("Hello", "1.2.0", package_id_text=None, requires=None)
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_version_mode()',
                     requires=["Hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install --build missing")
        self.assertIn("Hello2/2.3.8", self.conaninfo)

        # If we change the user and channel should not be needed to rebuild
        self._export("Hello", "1.2.0", package_id_text=None, requires=None, channel="memsharded/testing")
        self.client.run("install Hello/1.2.0@memsharded/testing --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_version_mode()',
                     requires=["Hello/1.2.0@memsharded/testing"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install .")
        self.assertIn("Hello2/2.3.8", self.conaninfo)

        # Now change the Hello version and build it, if we install out requires is
        # needed the --build needed because Hello2 needs to be build
        self._export("Hello", "1.5.0", package_id_text=None, requires=None)
        self.client.run("install Hello/1.5.0@lasote/stable --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_version_mode()',
                     requires=["Hello/1.5.0@lasote/stable"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install .", ignore_error=True)
        self.assertIn("Can't find a 'Hello2/2.3.8@lasote/stable' package", self.client.user_io.out)

    def test_version_full_recipe_schema(self):
        self._export("Hello", "1.2.0", package_id_text=None, requires=None)
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_recipe_mode()',
                     requires=["Hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install --build missing")
        self.assertIn("Hello2/2.3.8", self.conaninfo)

        # If we change the user and channel should be needed to rebuild
        self._export("Hello", "1.2.0", package_id_text=None, requires=None, channel="memsharded/testing")
        self.client.run("install Hello/1.2.0@memsharded/testing --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_recipe_mode()',
                     requires=["Hello/1.2.0@memsharded/testing"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install .", ignore_error=True)
        self.assertIn("Can't find a 'Hello2/2.3.8@lasote/stable' package", self.client.user_io.out)

        # If we change only the package ID from hello (one more defaulted option to True) should not affect
        self._export("Hello", "1.2.0", package_id_text=None, requires=None, default_option_value="on")
        self.client.run("install Hello/1.2.0@lasote/stable --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_recipe_mode()',
                     requires=["Hello/1.2.0@lasote/stable"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)

        self.client.run("install .")

    def test_version_full_package_schema(self):
        self._export("Hello", "1.2.0", package_id_text=None, requires=None)
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].full_package_mode()',
                     requires=["Hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install --build missing")
        self.assertIn("Hello2/2.3.8", self.conaninfo)

        # If we change only the package ID from hello (one more defaulted option to True) should affect
        self._export("Hello", "1.2.0", package_id_text=None, requires=None, default_option_value="on")
        self.client.run("install Hello/1.2.0@lasote/stable --build missing")
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install .", ignore_error=True)
        self.assertIn("Can't find a 'Hello2/2.3.8@lasote/stable' package", self.client.user_io.out)

    def test_nameless_mode(self):
        self._export("Hello", "1.2.0", package_id_text=None, requires=None)
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["Hello"].unrelated_mode()',
                     requires=["Hello/1.2.0@lasote/stable"])

        # Build the dependencies with --build missing
        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        self.client.run("install --build missing")
        self.assertIn("Hello2/2.3.8", self.conaninfo)

        # If we change even the require, should not affect
        self._export("HelloNew", "1.2.0")
        self.client.run("install HelloNew/1.2.0@lasote/stable --build missing")
        self._export("Hello2", "2.3.8",
                     package_id_text='self.info.requires["HelloNew"].unrelated_mode()',
                     requires=["HelloNew/1.2.0@lasote/stable"])

        self.client.save({"conanfile.txt": "[requires]\nHello2/2.3.8@lasote/stable"}, clean_first=True)
        # Not needed to rebuild Hello2, it doesn't matter its requires
        self.client.run("install .")
