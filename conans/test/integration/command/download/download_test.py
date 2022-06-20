import os
import unittest
from collections import OrderedDict

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import (TestClient, TestServer, NO_SETTINGS_PACKAGE_ID, TurboTestClient,
                                     GenConanfile)
from conans.util.files import load


class DownloadTest(unittest.TestCase):

    def test_download_recipe(self):
        client = TurboTestClient(default_server_user=True)
        # Test download of the recipe only
        conanfile = str(GenConanfile().with_name("pkg").with_version("0.1"))
        ref = RecipeReference.loads("pkg/0.1@lasote/stable")
        client.create(ref, conanfile)
        client.upload_all(ref)
        client.remove_all()

        client.run("download pkg/0.1@lasote/stable -r default")

        self.assertIn("Downloading conanfile.py", client.out)
        self.assertNotIn("Downloading conan_package.tgz", client.out)
        ref_layout = client.get_latest_ref_layout(ref)
        export = ref_layout.export()
        conan = ref_layout.base_folder
        self.assertTrue(os.path.exists(os.path.join(export, "conanfile.py")))
        self.assertEqual(conanfile, load(os.path.join(export, "conanfile.py")))
        self.assertFalse(os.path.exists(os.path.join(conan, "package")))

    def test_download_with_sources(self):
        client = TestClient(servers={"default": TestServer()}, inputs=["admin", "password"])
        conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    name = "pkg"
    version = "0.1"
    exports_sources = "*"
"""
        client.save({"conanfile.py": conanfile,
                     "file.h": "myfile.h",
                     "otherfile.cpp": "C++code"})
        client.run("export . --user=lasote --channel=stable")

        ref = RecipeReference.loads("pkg/0.1@lasote/stable")
        client.run("upload pkg/0.1@lasote/stable -r default")
        client.run("remove pkg/0.1@lasote/stable -f")

        client.run("download pkg/0.1@lasote/stable -r default")
        self.assertIn("Downloading conan_sources.tgz", client.out)
        source = client.get_latest_ref_layout(ref).export_sources()
        self.assertEqual("myfile.h", load(os.path.join(source, "file.h")))
        self.assertEqual("C++code", load(os.path.join(source, "otherfile.cpp")))

    def test_download_reference_without_packages(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile().with_name("pkg").with_version("0.1")})
        client.run("export . --user=user --channel=stable")
        client.run("upload pkg/0.1@user/stable -r default")
        client.run("remove pkg/0.1@user/stable -f")

        client.run("download pkg/0.1@user/stable#*:* -r default", assert_error=True)
        # Check 'No remote binary packages found' warning
        self.assertIn("There are no packages matching", client.out)
        # The recipe is not downloaded either
        client.run("list recipes pkg*")
        assert "There are no matching recipe references" in client.out

    def test_download_reference_with_packages(self):
        client = TurboTestClient(default_server_user=True)
        conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    name = "pkg"
    version = "0.1"
    settings = "os"
"""
        ref = RecipeReference.loads("pkg/0.1@lasote/stable")

        client.create(ref, conanfile)
        client.upload_all(ref)
        client.remove_all()

        client.run("download pkg/0.1@lasote/stable#*:* -r default")
        pref = client.get_latest_package_reference(ref)
        ref_layout = client.get_latest_ref_layout(ref)
        pkg_layout = client.get_latest_pkg_layout(pref)

        package_folder = pkg_layout.package()
        # Check not 'No remote binary packages found' warning
        self.assertNotIn("WARN: No remote binary packages found in remote", client.out)
        # Check at conanfile.py is downloaded
        self.assertTrue(os.path.exists(ref_layout.conanfile()))
        # Check package folder created
        self.assertTrue(os.path.exists(package_folder))

    def test_download_wrong_id(self):
        client = TurboTestClient(default_server_user=True)
        ref = RecipeReference.loads("pkg/0.1@lasote/stable")
        client.export(ref)
        rrev = client.exported_recipe_revision()
        client.upload_all(ref)
        client.remove_all()

        client.run("download pkg/0.1@lasote/stable#{}:wrong -r default".format(rrev),
                   assert_error=True)
        self.assertIn("ERROR: There are no packages matching "
                      "'pkg/0.1@lasote/stable#{}:wrong".format(rrev), client.out)

    def test_download_full_reference(self):
        server = TestServer()
        servers = {"default": server}

        client = TurboTestClient(servers=servers, inputs=["admin", "password"])

        ref = RecipeReference.loads("pkg/0.1")
        client.create(ref)
        client.upload_all(ref)
        client.remove_all()

        client.run("download pkg/0.1#*:{} -r default".format(NO_SETTINGS_PACKAGE_ID))

        rrev = client.cache.get_latest_recipe_reference(ref)
        pkgids = client.cache.get_package_references(rrev)
        prev = client.cache.get_latest_package_reference(pkgids[0])
        package_folder = client.cache.pkg_layout(prev).package()

        # Check not 'No remote binary packages found' warning
        self.assertNotIn("WARN: No remote binary packages found in remote", client.out)
        # Check at conanfile.py is downloaded
        self.assertTrue(os.path.exists(client.cache.ref_layout(rrev).conanfile()))
        # Check package folder created
        self.assertTrue(os.path.exists(package_folder))

    def test_download_with_package_query(self):
        client = TurboTestClient(default_server_user=True)
        conanfile = GenConanfile().with_settings("build_type")
        ref = RecipeReference.loads("pkg/0.1")
        first_ref = client.create(ref, conanfile=conanfile)
        client.upload_all(ref)
        client.remove_all()

        conanfile2 = str(conanfile) + " \n\n # new revision"
        client.create(ref, conanfile=conanfile2)
        client.create(ref, args="-s build_type=Debug", conanfile=conanfile2)
        client.upload_all(ref)
        client.remove_all()

        client.run("download pkg/0.1#latest -p 'build_type=Debug' -r default")
        client.run("list packages pkg/0.1#latest")
        assert "build_type=Debug" in client.out
        assert "build_type=Release" not in client.out

        client.run("download pkg/0.1#latest -p 'build_type=Release' -r default")
        client.run("list packages pkg/0.1#latest")
        assert "build_type=Debug" in client.out
        assert "build_type=Release" in client.out

        client.remove_all()
        client.run("list packages pkg/0.1#latest -r default")
        assert "build_type=Debug" in client.out
        assert "build_type=Release" in client.out

        client.remove_all()
        client.run("list packages pkg/0.1#{} -r default".format(first_ref.ref.revision))
        assert "build_type=Debug" not in client.out
        assert "build_type=Release" in client.out

    def test_download_package_argument(self):
        client = TurboTestClient(default_server_user=True)

        ref = RecipeReference.loads("pkg/0.1@lasote/stable")
        client.create(ref)
        client.upload_all(ref)
        client.remove_all()

        client.run("download pkg/0.1@lasote/stable#latest:{} -r default".format(NO_SETTINGS_PACKAGE_ID))

        rrev = client.cache.get_latest_recipe_reference(ref)
        pkgids = client.cache.get_package_references(rrev)
        prev = client.cache.get_latest_package_reference(pkgids[0])
        package_folder = client.cache.pkg_layout(prev).package()

        # Check not 'No remote binary packages found' warning
        self.assertNotIn("WARN: No remote binary packages found in remote", client.out)
        # Check at conanfile.py is downloaded
        self.assertTrue(os.path.exists(client.cache.ref_layout(rrev).conanfile()))
        # Check package folder created
        self.assertTrue(os.path.exists(package_folder))

    def test_download_not_found_reference(self):
        client = TurboTestClient(default_server_user=True)
        client.run("download pkg/0.1@lasote/stable -r default", assert_error=True)
        self.assertIn("ERROR: Recipe not found: 'pkg/0.1@lasote/stable'", client.out)

    def test_no_user_channel(self):
        # https://github.com/conan-io/conan/issues/6009
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=pkg --version=1.0")
        client.run("upload * --confirm -r default")
        client.run("remove * -f")

        client.run("download pkg/1.0#latest:{} -r default".format(NO_SETTINGS_PACKAGE_ID))
        self.assertIn("Downloading package 'pkg/1.0#4d670581ccb765839f2239cc8dff8fbd:%s" %
                      NO_SETTINGS_PACKAGE_ID, client.out)

        # All
        client.run("remove * -f")
        client.run("download pkg/1.0#*:* -r default")
        self.assertIn("Downloading package 'pkg/1.0#4d670581ccb765839f2239cc8dff8fbd:%s" %
                      NO_SETTINGS_PACKAGE_ID, client.out)

    def test_download_with_python_requires(self):
        """ when having a python_require in a different repo, it cannot be ``conan download``
        as the download runs from a single repo
        """
        # https://github.com/conan-io/conan/issues/9548
        servers = OrderedDict([("tools", TestServer()),
                               ("pkgs", TestServer())])
        c = TestClient(servers=servers, inputs=["admin", "password", "admin", "password"])

        c.save({"tool/conanfile.py": GenConanfile("tool", "0.1"),
                "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_python_requires("tool/0.1")})
        c.run("export tool")
        c.run("create pkg")
        c.run("upload tool* -r tools -c")
        c.run("upload pkg* -r pkgs -c")
        c.run("remove * -f")

        c.run("install --requires=pkg/0.1 -r pkgs -r tools")
        self.assertIn("Downloading", c.out)
        c.run("remove * -f")

        # FIXME: This fails, as it won't allow 2 remotes
        c.run("download pkg/0.1 -r pkgs -r tools")
        self.assertIn("Downloading", c.out)
        # FIXME: This fails, because the python_requires is not in the "pkgs" repo
        c.run("download pkg/0.1 -r pkgs")
        self.assertIn("Downloading", c.out)
