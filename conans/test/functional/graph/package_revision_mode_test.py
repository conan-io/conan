import textwrap
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class PackageRevisionModeTestCase(unittest.TestCase):

    def test_transtive_package_revision_mode(self):
        t = TestClient()
        t.save({
            'package1.py': GenConanfile("pkg1"),
            'package2.py': GenConanfile("pkg2").with_require_plain("pkg1/1.0"),
            'package3.py': textwrap.dedent("""
                from conans import ConanFile

                class Recipe(ConanFile):
                    requires = "pkg2/1.0"

                    def package_id(self):
                        self.info.requires["pkg1"].package_revision_mode()
            """)
        })
        t.run("create package1.py pkg1/1.0@")
        t.run("create package2.py pkg2/1.0@")

        # If we only build pkg1, we get a new packageID for pkg3
        t.run("create package3.py pkg3/1.0@ --build=pkg1")
        self.assertIn("pkg3/1.0:Package_ID_unknown - Unknown", t.out)
        self.assertIn("pkg3/1.0: Updated ID: 283642385cc7b64ec7b5903f6895107e0848d238", t.out)

        # If we build both, we get the new package
        t.run("create package3.py pkg3/1.0@ --build=pkg1 --build=pkg3")
        self.assertIn("pkg3/1.0:Package_ID_unknown - Unknown", t.out)
        self.assertIn("pkg3/1.0: Updated ID: 283642385cc7b64ec7b5903f6895107e0848d238", t.out)
        self.assertIn("pkg3/1.0: Package '283642385cc7b64ec7b5903f6895107e0848d238' created", t.out)
