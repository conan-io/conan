import os
import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient


class NoCopySourceTest(unittest.TestCase):

    def test_basic(self):
        conanfile = '''
from conan import ConanFile
from conan.tools.files import copy
from conans.util.files import save, load
import os

class ConanFileToolsTest(ConanFile):
    name = "pkg"
    version = "0.1"
    exports_sources = "*"
    no_copy_source = True

    def build(self):
        self.output.info("Source files: %s" % load(os.path.join(self.source_folder, "file.h")))
        save("myartifact.lib", "artifact contents!")

    def package(self):
        copy(self, "*", self.source_folder, self.package_folder)
        copy(self, "*", self.build_folder, self.package_folder)
'''

        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "file.h": "myfile.h contents"})
        client.run("export . --user=lasote --channel=testing")
        client.run("install --requires=pkg/0.1@lasote/testing --build='*'")
        self.assertIn("Source files: myfile.h contents", client.out)
        ref = RecipeReference.loads("pkg/0.1@lasote/testing")

        latest_rrev = client.cache.get_latest_recipe_reference(ref)
        pkg_ids = client.cache.get_package_references(latest_rrev)
        latest_prev = client.cache.get_latest_package_reference(pkg_ids[0])
        layout = client.cache.pkg_layout(latest_prev)
        build_folder = layout.build()
        package_folder = layout.package()

        self.assertNotIn("file.h", os.listdir(build_folder))
        self.assertIn("file.h", os.listdir(package_folder))
        self.assertIn("myartifact.lib", os.listdir(package_folder))

    @pytest.mark.xfail(reason="cache2.0 create --build not considered yet")
    def test_source_folder(self):
        conanfile = '''
from conan import ConanFile
from conans.util.files import save, load
from conan.tools.files import copy
import os

class ConanFileToolsTest(ConanFile):
    name = "pkg"
    version = "0.1"
    no_copy_source = %s

    def source(self):
        save("header.h", "artifact contents!")

    def package(self):
        copy(self, "*.h", self.source_folder, os.path.join(self.package_folder, "include"))
'''
        client = TestClient()
        client.save({"conanfile.py": conanfile % "True"})
        client.run("create . --user=lasote --channel=testing --build")
        ref = RecipeReference.loads("pkg/0.1@lasote/testing")

        latest_rrev = client.cache.get_latest_recipe_reference(ref)
        latest_prev = client.cache.get_latest_package_reference(latest_rrev)
        layout = client.cache.pkg_layout(latest_prev)
        package_folder = layout.package()

        self.assertIn("header.h", os.listdir(package_folder))

        client = TestClient()
        client.save({"conanfile.py": conanfile % "False"})
        client.run("create . --user=lasote --channel=testing --build")
        ref = RecipeReference.loads("pkg/0.1@lasote/testing")

        latest_rrev = client.cache.get_latest_recipe_reference(ref)
        latest_prev = client.cache.get_latest_package_reference(latest_rrev)
        layout = client.cache.pkg_layout(latest_prev)
        package_folder = layout.package()

        self.assertIn("header.h", os.listdir(package_folder))
