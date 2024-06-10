import os
import unittest

from conan.test.utils.tools import TestClient
from conans.util.files import load, mkdir

conanfile = '''
from conan import ConanFile
from conans.util.files import save, load
from conan.tools.files import copy
import os

class ConanFileToolsTest(ConanFile):
    name = "pkg"
    version = "0.1"
    exports_sources = "*"

    def layout(self):
        self.folders.build = "../build"
        self.folders.source = "."

    def build(self):
        self.output.info("Source files: %s" % load(os.path.join(self.source_folder, "file.h")))
        save("myartifact.lib", "artifact contents!")
        save("subdir/myartifact2.lib", "artifact2 contents!")

    def package(self):
        copy(self, "*.h", self.source_folder, self.package_folder)
        copy(self, "*.lib", self.build_folder, self.package_folder)
'''


class DevInSourceFlowTest(unittest.TestCase):

    def _assert_pkg(self, folder):
        self.assertEqual(sorted(['file.h', 'myartifact.lib', 'subdir', 'conaninfo.txt',
                                 'conanmanifest.txt']),
                         sorted(os.listdir(folder)))
        self.assertEqual(load(os.path.join(folder, "myartifact.lib")),
                         "artifact contents!")
        self.assertEqual(load(os.path.join(folder, "subdir/myartifact2.lib")),
                         "artifact2 contents!")

    def test_parallel_folders(self):
        client = TestClient()
        repo_folder = os.path.join(client.current_folder, "recipe")
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(repo_folder)
        mkdir(build_folder)

        client.current_folder = repo_folder  # equivalent to git clone recipe
        client.save({"conanfile.py": conanfile,
                     "file.h": "file_h_contents!"})

        client.current_folder = build_folder
        client.run("install ../recipe")
        client.run("build ../recipe")
        client.current_folder = repo_folder
        client.run("export . --user=lasote --channel=testing")
        client.run("export-pkg . --name=pkg --version=0.1 --user=lasote --channel=testing")

        cache_package_folder = client.created_layout().package()
        self._assert_pkg(cache_package_folder)

    def test_insource_build(self):
        client = TestClient()
        repo_folder = client.current_folder
        package_folder = os.path.join(client.current_folder, "pkg")
        mkdir(package_folder)
        client.save({"conanfile.py": conanfile,
                     "file.h": "file_h_contents!"})

        client.run("install .")
        client.run("build .")
        client.current_folder = repo_folder
        client.run("export . --user=lasote --channel=testing")
        client.run("export-pkg . --name=pkg --version=0.1 --user=lasote --channel=testing")

        cache_package_folder = client.created_layout().package()
        self._assert_pkg(cache_package_folder)

    def test_child_build(self):
        client = TestClient()
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        package_folder = os.path.join(build_folder, "package")
        mkdir(package_folder)
        client.save({"conanfile.py": conanfile,
                     "file.h": "file_h_contents!"})

        client.current_folder = build_folder
        client.run("install ..")
        client.run("build ..")
        client.run("export-pkg .. --name=pkg --version=0.1 --user=lasote --channel=testing")

        cache_package_folder = client.created_layout().package()
        self._assert_pkg(cache_package_folder)


conanfile_out = '''
from conan import ConanFile
from conans.util.files import save, load
from conan.tools.files import copy
import os

class ConanFileToolsTest(ConanFile):
    name = "pkg"
    version = "0.1"

    def source(self):
        save(os.path.join(self.source_folder, "file.h"), "file_h_contents!")

    def build(self):
        self.output.info("Source files: %s" % load(os.path.join(self.source_folder, "file.h")))
        save("myartifact.lib", "artifact contents!")

    def package(self):
        copy(self, "*.h", self.source_folder, self.package_folder)
        copy(self, "*.lib", self.build_folder, self.package_folder)
'''


class DevOutSourceFlowTest(unittest.TestCase):

    def _assert_pkg(self, folder):
        self.assertEqual(sorted(['file.h', 'myartifact.lib', 'conaninfo.txt', 'conanmanifest.txt']),
                         sorted(os.listdir(folder)))

    def test_parallel_folders(self):
        client = TestClient()
        repo_folder = os.path.join(client.current_folder, "recipe")
        src_folder = os.path.join(client.current_folder, "src")
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(repo_folder)
        mkdir(src_folder)
        mkdir(build_folder)
        client.current_folder = repo_folder  # equivalent to git clone recipe
        conanfile_final = conanfile_out + """
    def layout(self):
        self.folders.build = "../build"
        self.folders.source = "../src"
        """
        client.save({"conanfile.py": conanfile_final})

        client.current_folder = build_folder
        client.run("install ../recipe")
        client.current_folder = src_folder  # FIXME: Source layout not working
        client.run("source ../recipe")

        client.current_folder = build_folder
        client.run("build ../recipe")
        client.current_folder = repo_folder
        client.run("export . --user=lasote --channel=testing")
        client.run("export-pkg . --name=pkg --version=0.1 --user=lasote --channel=testing")

        cache_package_folder = client.created_layout().package()
        self._assert_pkg(cache_package_folder)

    def test_insource_build(self):
        client = TestClient()
        repo_folder = client.current_folder
        client.save({"conanfile.py": conanfile_out})

        client.run("install .")
        client.run("source .")
        client.run("build . ")

        client.current_folder = repo_folder
        client.run("export . --user=lasote --channel=testing")
        client.run("export-pkg . --name=pkg --version=0.1 --user=lasote --channel=testing")

        cache_package_folder = client.created_layout().package()
        self._assert_pkg(cache_package_folder)

    def test_child_build(self):
        client = TestClient()
        repo_folder = client.current_folder
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        conanfile_final = conanfile_out + """
    def layout(self):
        self.folders.build = "build"
        """
        client.save({"conanfile.py": conanfile_final})

        client.current_folder = build_folder
        client.run("install ..")
        client.current_folder = repo_folder  # FIXME: Source layout not working
        client.run("source .")
        client.current_folder = build_folder
        client.run("build ..")
        client.current_folder = repo_folder

        client.run("export-pkg . --name=pkg --version=0.1 --user=lasote --channel=testing")

        cache_package_folder = client.created_layout().package()
        self._assert_pkg(cache_package_folder)
