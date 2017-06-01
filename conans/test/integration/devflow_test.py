import unittest
from conans.test.utils.tools import TestClient
import os
from conans.util.files import mkdir, load
from conans.model.ref import ConanFileReference


conanfile = '''
from conans import ConanFile
from conans.util.files import save, load
import os

class ConanFileToolsTest(ConanFile):
    name = "Pkg"
    version = "0.1"
    exports_sources = "*"
    generators = "cmake"

    def build(self):
        self.output.info("Source files: %s" % load(os.path.join(self.source_folder, "file.h")))
        save("myartifact.lib", "artifact contents!")
        save("subdir/myartifact2.lib", "artifact2 contents!")

    def package(self):
        self.copy("*.h")
        self.copy("*.lib")
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

    def parallel_folders_test(self):
        client = TestClient()
        repo_folder = os.path.join(client.current_folder, "recipe")
        build_folder = os.path.join(client.current_folder, "build")
        package_folder = os.path.join(client.current_folder, "pkg")
        mkdir(repo_folder)
        mkdir(build_folder)
        mkdir(package_folder)
        client.current_folder = repo_folder  # equivalent to git clone recipe
        client.save({"conanfile.py": conanfile,
                     "file.h": "file_h_contents!"})

        client.current_folder = build_folder
        client.run("install ../recipe -g txt")
        client.run("build ../recipe")
        client.current_folder = package_folder
        client.run("package ../recipe --build_folder=../build")
        self._assert_pkg(package_folder)
        client.current_folder = repo_folder
        client.run("export lasote/testing")
        client.run("package_files Pkg/0.1@lasote/testing -pf=../pkg")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        cache_package_folder = client.client_cache.packages(ref)
        cache_package_folder = os.path.join(cache_package_folder,
                                            os.listdir(cache_package_folder)[0])
        self._assert_pkg(cache_package_folder)

    def insource_build_test(self):
        client = TestClient()
        repo_folder = client.current_folder
        package_folder = os.path.join(client.current_folder, "pkg")
        mkdir(package_folder)
        client.save({"conanfile.py": conanfile,
                     "file.h": "file_h_contents!"})

        client.run("install . -g txt")
        client.run("build .")
        client.current_folder = package_folder
        client.run("package .. --build_folder=..")
        self._assert_pkg(package_folder)
        client.current_folder = repo_folder
        client.run("export lasote/testing")
        client.run("package_files Pkg/0.1@lasote/testing -pf=./pkg")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        cache_package_folder = client.client_cache.packages(ref)
        cache_package_folder = os.path.join(cache_package_folder,
                                            os.listdir(cache_package_folder)[0])
        self._assert_pkg(cache_package_folder)

    def child_build_test(self):
        client = TestClient()
        repo_folder = client.current_folder
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        package_folder = os.path.join(client.current_folder, "pkg")
        mkdir(package_folder)
        client.save({"conanfile.py": conanfile,
                     "file.h": "file_h_contents!"})

        client.current_folder = build_folder
        client.run("install .. -g txt")
        client.run("build ..")
        client.current_folder = package_folder
        client.run("package .. --build_folder=../build")
        self._assert_pkg(package_folder)
        client.current_folder = repo_folder
        client.run("export lasote/testing")
        client.run("package_files Pkg/0.1@lasote/testing -pf=./pkg")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        cache_package_folder = client.client_cache.packages(ref)
        cache_package_folder = os.path.join(cache_package_folder,
                                            os.listdir(cache_package_folder)[0])
        self._assert_pkg(cache_package_folder)


conanfile_out = '''
from conans import ConanFile
from conans.util.files import save, load
import os

class ConanFileToolsTest(ConanFile):
    name = "Pkg"
    version = "0.1"
    generators = "cmake"

    def source(self):
        save("file.h", "file_h_contents!")

    def build(self):
        self.output.info("Source files: %s" % load(os.path.join(self.source_folder, "file.h")))
        save("myartifact.lib", "artifact contents!")

    def package(self):
        self.copy("*.h")
        self.copy("*.lib")
'''


class DevOutSourceFlowTest(unittest.TestCase):

    def _assert_pkg(self, folder):
        self.assertEqual(sorted(['file.h', 'myartifact.lib', 'conaninfo.txt', 'conanmanifest.txt']),
                         sorted(os.listdir(folder)))

    def parallel_folders_test(self):
        client = TestClient()
        repo_folder = os.path.join(client.current_folder, "recipe")
        src_folder = os.path.join(client.current_folder, "src")
        build_folder = os.path.join(client.current_folder, "build")
        package_folder = os.path.join(client.current_folder, "pkg")
        mkdir(repo_folder)
        mkdir(src_folder)
        mkdir(build_folder)
        mkdir(package_folder)
        client.current_folder = repo_folder  # equivalent to git clone recipe
        client.save({"conanfile.py": conanfile_out})

        client.current_folder = build_folder
        client.run("install ../recipe -g txt")
        client.current_folder = src_folder
        client.run("source ../recipe")
        client.current_folder = build_folder
        client.run("build ../recipe --source_folder=../src")
        client.current_folder = package_folder
        client.run("package ../recipe --source_folder=../src --build_folder=../build")
        self._assert_pkg(package_folder)
        client.current_folder = repo_folder
        client.run("export lasote/testing")
        client.run("package_files Pkg/0.1@lasote/testing -pf=../pkg")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        cache_package_folder = client.client_cache.packages(ref)
        cache_package_folder = os.path.join(cache_package_folder,
                                            os.listdir(cache_package_folder)[0])
        self._assert_pkg(cache_package_folder)

    def insource_build_test(self):
        client = TestClient()
        repo_folder = client.current_folder
        package_folder = os.path.join(client.current_folder, "pkg")
        mkdir(package_folder)
        client.save({"conanfile.py": conanfile_out})

        client.run("install . -g txt")
        client.run("source .")
        client.run("build . ")
        client.current_folder = package_folder
        client.run("package .. --build_folder=..")
        self._assert_pkg(package_folder)
        client.current_folder = repo_folder
        client.run("export lasote/testing")
        client.run("package_files Pkg/0.1@lasote/testing -pf=./pkg")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        cache_package_folder = client.client_cache.packages(ref)
        cache_package_folder = os.path.join(cache_package_folder,
                                            os.listdir(cache_package_folder)[0])
        self._assert_pkg(cache_package_folder)

    def child_build_test(self):
        client = TestClient()
        repo_folder = client.current_folder
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        package_folder = os.path.join(client.current_folder, "pkg")
        mkdir(package_folder)
        client.save({"conanfile.py": conanfile_out})

        client.current_folder = build_folder
        client.run("install .. -g txt")
        client.run("source ..")
        client.run("build .. --source_folder=.")
        client.current_folder = package_folder
        client.run("package .. --build_folder=../build")
        self._assert_pkg(package_folder)
        client.current_folder = repo_folder
        client.run("export lasote/testing")
        client.run("package_files Pkg/0.1@lasote/testing -pf=./pkg")

        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        cache_package_folder = client.client_cache.packages(ref)
        cache_package_folder = os.path.join(cache_package_folder,
                                            os.listdir(cache_package_folder)[0])
        self._assert_pkg(cache_package_folder)
