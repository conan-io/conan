import os
import unittest
from collections import OrderedDict

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient, TestServer, NO_SETTINGS_PACKAGE_ID, GenConanfile
from conans.util.files import load


class DownloadTest(unittest.TestCase):

    def test_download_with_sources(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile("pkg", "0.1").with_exports_sources("*"),
                     "file.h": "myfile.h",
                     "otherfile.cpp": "C++code"})
        client.run("export . --user=lasote --channel=stable")

        ref = RecipeReference.loads("pkg/0.1@lasote/stable")
        client.run("upload pkg/0.1@lasote/stable -r default")
        client.run("remove pkg/0.1@lasote/stable -c")

        client.run("download pkg/0.1@lasote/stable -r default")
        self.assertIn("Downloading 'pkg/0.1@lasote/stable' sources", client.out)
        source = client.get_latest_ref_layout(ref).export_sources()
        self.assertEqual("myfile.h", load(os.path.join(source, "file.h")))
        self.assertEqual("C++code", load(os.path.join(source, "otherfile.cpp")))

    def test_no_user_channel(self):
        # https://github.com/conan-io/conan/issues/6009
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=pkg --version=1.0")
        client.run("upload * --confirm -r default")
        client.run("remove * -c")

        client.run("download pkg/1.0:{} -r default".format(NO_SETTINGS_PACKAGE_ID))
        self.assertIn("Downloading package 'pkg/1.0#4d670581ccb765839f2239cc8dff8fbd:%s" %
                      NO_SETTINGS_PACKAGE_ID, client.out)

        # All
        client.run("remove * -c")
        client.run("download pkg/1.0#*:* -r default")
        self.assertIn("Downloading package 'pkg/1.0#4d670581ccb765839f2239cc8dff8fbd:%s" %
                      NO_SETTINGS_PACKAGE_ID, client.out)

    def test_download_with_python_requires(self):
        """ In the past,
        when having a python_require in a different repo, it cannot be ``conan download``
        as the download runs from a single repo.

        Now, from https://github.com/conan-io/conan/issues/14260, "conan download" doesn't
        really need to load conanfile, so it doesn't fail because of this.
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
        c.run("remove * -c")

        c.run("install --requires=pkg/0.1 -r pkgs -r tools")
        self.assertIn("Downloading", c.out)
        c.run("remove * -c")

        c.run("download pkg/0.1 -r pkgs")
        assert "pkg/0.1: Downloaded package revision" in c.out
