import os
import unittest

from conans.model.recipe_ref import RecipeReference
from conans.paths import CONANFILE
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class OnlySourceTest(unittest.TestCase):

    def test_conan_test(self):
        # Checks --build in test command
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("hello0", "0.0")})
        client.run("export . --user=lasote --channel=stable")
        client.save({"conanfile.py": GenConanfile("hello1", "1.1").
                    with_require("hello0/0.0@lasote/stable")})
        client.run("export . --user=lasote --channel=stable")

        # Now test out Hello2
        client.save({"conanfile.py": GenConanfile("hello2", "2.2").
                    with_require("hello1/1.1@lasote/stable"),
                     "test/conanfile.py": GenConanfile().with_test("pass")})

        # Should recognize the hello package
        # Will Fail because hello0/0.0 and hello1/1.1 has not built packages
        # and by default no packages are built
        client.run("create . --user=lasote --channel=stable", assert_error=True)
        self.assertIn("Or try to build locally from sources with '--build=hello0 --build=hello1'",
                      client.out)
        # Only 1 reference!
        assert "Use 'conan search hello0/0.0@lasote/stable --table=table.html" in client.out

        # We generate the package for hello0/0.0
        client.run("install --reference=hello0/0.0@lasote/stable --build hello0")

        # Still missing hello1/1.1
        client.run("create . --user=lasote --channel=stable", assert_error=True)
        self.assertIn("Or try to build locally from sources with '--build=hello1'", client.out)

        # We generate the package for hello1/1.1
        client.run("install --reference=hello1/1.1@lasote/stable --build hello1")

        # Now Hello2 should be built and not fail
        client.run("create . --user=lasote --channel=stable")
        self.assertNotIn("Can't find a 'hello2/2.2@lasote/stable' package", client.out)
        self.assertIn('hello2/2.2@lasote/stable: Forced build from source', client.out)

        # Now package is generated but should be built again
        client.run("create . --user=lasote --channel=stable")
        self.assertIn('hello2/2.2@lasote/stable: Forced build from source', client.out)

    def test_build_policies_update(self):
        client = TestClient(default_server_user=True)
        conanfile = """
from conans import ConanFile

class MyPackage(ConanFile):
    name = "test"
    version = "1.9"
    build_policy = 'always'

    def source(self):
        self.output.info("Getting sources")
    def build(self):
        self.output.info("Building sources")
    def package(self):
        self.output.info("Packaging this test package")
        """

        files = {CONANFILE: conanfile}
        client.save(files, clean_first=True)
        client.run("export . --user=lasote --channel=stable")
        client.run("install --reference=test/1.9@lasote/stable")
        self.assertIn("Getting sources", client.out)
        self.assertIn("Building sources", client.out)
        self.assertIn("Packaging this test package", client.out)
        self.assertIn("Building package from source as defined by build_policy='always'",
                      client.out)
        client.run("upload test/1.9@lasote/stable -r default")

    def test_build_policies_in_conanfile(self):
        client = TestClient(default_server_user=True)
        base = GenConanfile("hello0", "1.0").with_exports("*")
        conanfile = str(base) + "\n    build_policy = 'missing'"
        client.save({"conanfile.py": conanfile})
        client.run("export . --user=lasote --channel=stable")

        # Install, it will build automatically if missing (without the --build missing option)
        client.run("install --reference=hello0/1.0@lasote/stable")
        self.assertIn("Building", client.out)

        # Try to do it again, now we have the package, so no build is done
        client.run("install --reference=hello0/1.0@lasote/stable")
        self.assertNotIn("Building", client.out)

        # Try now to upload all packages, should not crash because of the "missing" build policy
        client.run("upload hello0/1.0@lasote/stable --all -r default")

        #  --- Build policy to always ---
        conanfile = str(base) + "\n    build_policy = 'always'"
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("export . --user=lasote --channel=stable")

        # Install, it will build automatically if missing (without the --build missing option)
        client.run("install --reference=hello0/1.0@lasote/stable")
        self.assertIn("Detected build_policy 'always', trying to remove source folder",
                      client.out)
        self.assertIn("Building", client.out)

        # Try to do it again, now we have the package, but we build again
        client.run("install --reference=hello0/1.0@lasote/stable")
        self.assertIn("Building", client.out)
        self.assertIn("Detected build_policy 'always', trying to remove source folder",
                      client.out)

        # Try now to upload all packages, should crash because of the "always" build policy
        client.run("upload hello0/1.0@lasote/stable --all -r default", assert_error=True)
        self.assertIn("no packages can be uploaded", client.out)

    def test_reuse(self):
        client = TestClient(default_server_user=True)
        ref = RecipeReference.loads("hello0/0.1@lasote/stable")
        client.save({"conanfile.py": GenConanfile("hello0", "0.1")})
        client.run("export . --user=lasote --channel=stable")
        client.run("install --reference=%s --build missing" % str(ref))
        pref = client.get_latest_package_reference(ref)
        self.assertTrue(os.path.exists(client.get_latest_pkg_layout(pref).build()))
        self.assertTrue(os.path.exists(client.get_latest_pkg_layout(pref).package()))

        # Upload
        client.run("upload %s --all -r default" % str(ref))

        # Now from other "computer" install the uploaded conans with same options (nothing)
        other_client = TestClient(servers=client.servers)
        other_client.run("install --reference=%s --build missing" % str(ref))
        pref = client.get_latest_package_reference(ref)
        self.assertFalse(os.path.exists(other_client.get_latest_pkg_layout(pref).build()))
        self.assertTrue(os.path.exists(other_client.get_latest_pkg_layout(pref).package()))

        # Now from other "computer" install the uploaded conans with same options (nothing)
        other_client = TestClient(servers=client.servers)
        other_client.run("install --reference=%s --build" % str(ref))
        pref = client.get_latest_package_reference(ref)
        self.assertTrue(os.path.exists(other_client.get_latest_pkg_layout(pref).build()))
        self.assertTrue(os.path.exists(other_client.get_latest_pkg_layout(pref).package()))

        # Use an invalid pattern and check that its not builded from source
        other_client = TestClient(servers=client.servers)
        other_client.run("install --reference=%s --build HelloInvalid" % str(ref))

        # pref = client.get_latest_package_reference(ref)
        # self.assertIn("No package matching 'HelloInvalid' pattern", other_client.out)
        # self.assertFalse(os.path.exists(other_client.get_latest_pkg_layout(pref).build()))

        # Use another valid pattern and check that its not builded from source
        other_client = TestClient(servers=client.servers)
        other_client.run("install --reference=%s --build HelloInvalid -b hello" % str(ref))
        # self.assertIn("No package matching 'HelloInvalid' pattern", other_client.out)

        # Now even if the package is in local store, check that's rebuilded
        other_client.run("install --reference=%s -b hello*" % str(ref))
        self.assertIn("Copying sources to build folder", other_client.out)

        other_client.run("install --reference=%s" % str(ref))
        self.assertNotIn("Copying sources to build folder", other_client.out)
