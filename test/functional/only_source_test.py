import os
import unittest

from conans.model.recipe_ref import RecipeReference
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


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
        self.assertIn("Try to build locally from sources using the '--build=hello0/0.0@lasote/stable "
                      "--build=hello1/1.1@lasote/stable'",
                      client.out)
        # Only 1 reference!
        assert "List all available packages using 'conan list \"hello0/0.0@lasote/stable:*\" -r=remote'" in client.out

        # We generate the package for hello0/0.0
        client.run("install --requires=hello0/0.0@lasote/stable --build hello0*")

        # Still missing hello1/1.1
        client.run("create . --user=lasote --channel=stable", assert_error=True)
        self.assertIn("Try to build locally from sources using the "
                      "'--build=hello1/1.1@lasote/stable'", client.out)

        # We generate the package for hello1/1.1
        client.run("install --requires=hello1/1.1@lasote/stable --build hello1*")

        # Now Hello2 should be built and not fail
        client.run("create . --user=lasote --channel=stable")
        self.assertNotIn("Can't find a 'hello2/2.2@lasote/stable' package", client.out)
        self.assertIn('hello2/2.2@lasote/stable: Forced build from source', client.out)

        # Now package is generated but should be built again
        client.run("create . --user=lasote --channel=stable")
        self.assertIn('hello2/2.2@lasote/stable: Forced build from source', client.out)

    def test_build_policies_in_conanfile(self):
        client = TestClient(default_server_user=True)
        base = GenConanfile("hello0", "1.0").with_exports("*")
        conanfile = str(base) + "\n    build_policy = 'missing'"
        client.save({"conanfile.py": conanfile})
        client.run("export . --user=lasote --channel=stable")

        # Install, it will build automatically if missing (without the --build missing option)
        client.run("install --requires=hello0/1.0@lasote/stable")
        self.assertIn("Building", client.out)

        # Try to do it again, now we have the package, so no build is done
        client.run("install --requires=hello0/1.0@lasote/stable")
        self.assertNotIn("Building", client.out)

        # Try now to upload all packages, should not crash because of the "missing" build policy
        client.run("upload hello0/1.0@lasote/stable -r default")

        #  --- Build policy to always ---
        conanfile = str(base) + "\n    build_policy = 'always'"
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("export . --user=lasote --channel=stable")

        # Install, it will build automatically if missing (without the --build missing option)
        client.run("install --requires=hello0/1.0@lasote/stable", assert_error=True)
        self.assertIn("ERROR: hello0/1.0@lasote/stable: build_policy='always' has been removed",
                      client.out)

    def test_reuse(self):
        client = TestClient(default_server_user=True)
        ref = RecipeReference.loads("hello0/0.1@lasote/stable")
        client.save({"conanfile.py": GenConanfile("hello0", "0.1")})
        client.run("export . --user=lasote --channel=stable")
        client.run("install --requires=%s --build missing" % str(ref))
        pkg_layout = client.created_layout()
        self.assertTrue(os.path.exists(pkg_layout.build()))
        self.assertTrue(os.path.exists(pkg_layout.package()))

        # Upload
        client.run("upload %s -r default" % str(ref))

        # Now from other "computer" install the uploaded conans with same options (nothing)
        other_client = TestClient(servers=client.servers)
        other_client.run("install --requires=%s --build missing" % str(ref))
        pref = client.get_latest_package_reference(ref)
        self.assertFalse(os.path.exists(other_client.get_latest_pkg_layout(pref).build()))
        self.assertTrue(os.path.exists(other_client.get_latest_pkg_layout(pref).package()))

        # Now from other "computer" install the uploaded conans with same options (nothing)
        other_client = TestClient(servers=client.servers)
        other_client.run("install --requires=%s --build='*'" % str(ref))
        pkg_layout = other_client.created_layout()
        self.assertTrue(os.path.exists(pkg_layout.build()))
        self.assertTrue(os.path.exists(pkg_layout.package()))

        # Use an invalid pattern and check that its not builded from source
        other_client = TestClient(servers=client.servers)
        other_client.run("install --requires=%s --build HelloInvalid" % str(ref))

        # pref = client.get_latest_package_reference(ref)
        # self.assertIn("No package matching 'HelloInvalid' pattern", other_client.out)
        # self.assertFalse(os.path.exists(other_client.get_latest_pkg_layout(pref).build()))

        # Use another valid pattern and check that its not builded from source
        other_client = TestClient(servers=client.servers)
        other_client.run("install --requires=%s --build HelloInvalid -b hello" % str(ref))
        # self.assertIn("No package matching 'HelloInvalid' pattern", other_client.out)

        # Now even if the package is in local store, check that's rebuilded
        other_client.run("install --requires=%s -b hello*" % str(ref))
        self.assertIn("Copying sources to build folder", other_client.out)

        other_client.run("install --requires=%s" % str(ref))
        self.assertNotIn("Copying sources to build folder", other_client.out)


def test_build_policy_missing():
    c = TestClient(default_server_user=True)
    conanfile = GenConanfile("pkg", "1.0").with_class_attribute('build_policy = "missing"')\
                                          .with_class_attribute('upload_policy = "skip"')
    c.save({"conanfile.py": conanfile})
    c.run("export .")

    # the --build=never has higher priority
    c.run("install --requires=pkg/1.0@ --build=never", assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkg/1.0'" in c.out

    c.run("install --requires=pkg/1.0@")
    assert "pkg/1.0: Building package from source as defined by build_policy='missing'" in c.out

    # If binary already there it should do nothing
    c.run("install --requires=pkg/1.0@")
    assert "pkg/1.0: Building package from source" not in c.out

    c.run("upload * -r=default -c")
    assert "Uploading package" not in c.out
    assert "pkg/1.0: Skipping upload of binaries, because upload_policy='skip'" in c.out
