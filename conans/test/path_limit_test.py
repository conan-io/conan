import unittest
from conans.test.tools import TestClient
from conans.util.files import load
import os
from conans.model.ref import PackageReference, ConanFileReference
import platform


class PathLengthLimitTest(unittest.TestCase):

    def basic_test(self):
        client = TestClient()
        base = '''
from conans import ConanFile
from conans.util.files import load, save
import os

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    short_paths = True

    def source(self):
        extra_path = "1/" * 108
        os.makedirs(extra_path)
        myfile = os.path.join(extra_path, "myfile.txt")
        # print("File length ", len(myfile))
        save(myfile, "Hello extra path length")

    def build(self):
        extra_path = "1/" * 108
        myfile = os.path.join(extra_path, "myfile2.txt")
        # print("File length ", len(myfile))
        save(myfile, "Hello2 extra path length")

    def package(self):
        self.copy("*.txt", keep_path=False)
'''

        files = {"conanfile.py": base}
        client.save(files)
        client.run("export user/channel")
        client.run("install lib/0.1@user/channel --build")
        package_ref = PackageReference.loads("lib/0.1@user/channel:"
                                             "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_folder = client.client_cache.package(package_ref, short_paths=None)
        file1 = load(os.path.join(package_folder, "myfile.txt"))
        self.assertEqual("Hello extra path length", file1)
        file2 = load(os.path.join(package_folder, "myfile2.txt"))
        self.assertEqual("Hello2 extra path length", file2)

        if platform.system() == "Windows":
            conan_ref = ConanFileReference.loads("lib/0.1@user/channel")
            source_folder = client.client_cache.source(conan_ref)
            link_source = load(os.path.join(source_folder, ".conan_link"))
            self.assertTrue(os.path.exists(link_source))

            build_folder = client.client_cache.build(package_ref)
            link_build = load(os.path.join(build_folder, ".conan_link"))
            self.assertTrue(os.path.exists(link_build))

            package_folder = client.client_cache.package(package_ref)
            link_package = load(os.path.join(package_folder, ".conan_link"))
            self.assertTrue(os.path.exists(link_package))

            client.run("remove lib* -f")
            self.assertFalse(os.path.exists(link_source))
            self.assertFalse(os.path.exists(link_build))
            self.assertFalse(os.path.exists(link_package))
