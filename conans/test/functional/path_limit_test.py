import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load
import os
from conans.model.ref import PackageReference, ConanFileReference
from conans.tools import environment_append
from conans.test import CONAN_TEST_FOLDER
import tempfile
import platform


base = '''
from conans import ConanFile
from conans.util.files import load, save
import os

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    short_paths = True
    exports_sources = "*"

    def source(self):
        extra_path = "1/" * 90
        os.makedirs(extra_path)
        myfile = os.path.join(extra_path, "myfile.txt")
        # print("File length ", len(myfile))
        save(myfile, "Hello extra path length")

    def build(self):
        extra_path = "1/" * 90
        myfile = os.path.join(extra_path, "myfile2.txt")
        # print("File length ", len(myfile))
        save(myfile, "Hello2 extra path length")

    def package(self):
        self.copy("*.txt", keep_path=False)
'''


class PathLengthLimitTest(unittest.TestCase):

    def remove_test(self):
        short_home = tempfile.mkdtemp(dir=CONAN_TEST_FOLDER)
        client = TestClient()
        files = {"conanfile.py": base,
                 "path/"*20 + "file0.txt": "file0 content"}  # shorten to pass appveyor
        client.save(files)
        with environment_append({"CONAN_USER_HOME_SHORT": short_home}):
            client.run("export . lasote/channel")
            client.run("install lib/0.1@lasote/channel --build")
            client.run('remove "lib*" -b -p -f')
            client.run("install lib/0.1@lasote/channel --build")
            client.run('remove "lib*" -s -f')
            client.run("install lib/0.1@lasote/channel --build")
            client.run('remove "*" -f')
            self.assertEqual(len(os.listdir(short_home)), 0)

    def upload_test(self):
        test_server = TestServer([],  # write permissions
                                 users={"lasote": "mypass"})  # exported users and passwords
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        files = {"conanfile.py": base}
        client.save(files)
        client.run("export . lasote/channel")
        client.run("install lib/0.1@lasote/channel --build")
        client.run("upload lib/0.1@lasote/channel --all")
        client.run("remove lib/0.1@lasote/channel -f")
        client.run("search")
        self.assertIn("There are no packages", client.user_io.out)

        for command in ("install", "download"):
            client2 = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
            client2.run("%s lib/0.1@lasote/channel" % command)
            reference = ConanFileReference.loads("lib/0.1@lasote/channel")
            export_folder = client2.client_cache.export(reference)
            export_files = os.listdir(export_folder)
            self.assertNotIn('conan_export.tgz', export_files)
            package_ref = PackageReference.loads("lib/0.1@lasote/channel:"
                                                 "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
            package_folder = client2.client_cache.package(package_ref, short_paths=None)
            if platform.system() == "Windows":
                original_folder = client2.client_cache.package(package_ref)
                link = load(os.path.join(original_folder, ".conan_link"))
                self.assertEqual(link, package_folder)

            files = os.listdir(package_folder)
            self.assertIn("myfile.txt", files)
            self.assertIn("myfile2.txt", files)
            self.assertNotIn("conan_package.tgz", files)

    def export_source_test(self):
        client = TestClient()
        files = {"conanfile.py": base,
                 "path/"*20 + "file0.txt": "file0 content"}
        client.save(files)
        client.run("export . user/channel")
        conan_ref = ConanFileReference.loads("lib/0.1@user/channel")
        source_folder = client.client_cache.export_sources(conan_ref)
        if platform.system() == "Windows":
            source_folder = load(os.path.join(source_folder, ".conan_link"))
        self.assertTrue(os.path.exists(source_folder))
        self.assertEqual(load(os.path.join(source_folder + "/path"*20 + "/file0.txt")),
                         "file0 content")
        client.run("install lib/0.1@user/channel --build=missing")
        package_ref = PackageReference.loads("lib/0.1@user/channel:"
                                             "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_folder = client.client_cache.package(package_ref)
        if platform.system() == "Windows":
            package_folder = load(os.path.join(package_folder, ".conan_link"))
        self.assertTrue(os.path.exists(package_folder))
        self.assertEqual(load(os.path.join(package_folder + "/file0.txt")), "file0 content")

    def package_copier_test(self):
        client = TestClient()
        files = {"conanfile.py": base}
        client.save(files)
        client.run("export . lasote/channel")
        client.run("install lib/0.1@lasote/channel --build")
        client.run("copy lib/0.1@lasote/channel memsharded/stable --all")
        client.run("search")
        self.assertIn("lib/0.1@lasote/channel", client.user_io.out)
        self.assertIn("lib/0.1@memsharded/stable", client.user_io.out)
        client.run("search lib/0.1@lasote/channel")
        self.assertIn("Package_ID: 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", client.user_io.out)
        client.run("search lib/0.1@memsharded/stable")
        self.assertIn("Package_ID: 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", client.user_io.out)

        conan_ref = ConanFileReference.loads("lib/0.1@lasote/channel")
        package_ref = PackageReference(conan_ref, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_folder = client.client_cache.package(package_ref)
        if platform.system() == "Windows":
            package_folder = load(os.path.join(package_folder, ".conan_link"))
        self.assertTrue(os.path.exists(package_folder))

    def basic_test(self):
        client = TestClient()
        files = {"conanfile.py": base}
        client.save(files)
        client.run("export . user/channel")
        client.run("install lib/0.1@user/channel --build")
        package_ref = PackageReference.loads("lib/0.1@user/channel:"
                                             "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        client.run("search")
        self.assertIn("lib/0.1@user/channel", client.user_io.out)
        client.run("search lib/0.1@user/channel")
        self.assertIn("Package_ID: 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", client.user_io.out)

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

    def basic_disabled_test(self):
        client = TestClient()
        base = '''
from conans import ConanFile

class ConanLib(ConanFile):
    short_paths = True
'''
        client.save({"conanfile.py": base})

        client.run("create . lib/0.1@user/channel")
        package_ref = PackageReference.loads("lib/0.1@user/channel:"
                                             "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        client.run("search")
        self.assertIn("lib/0.1@user/channel", client.user_io.out)
        client.run("search lib/0.1@user/channel")
        self.assertIn("Package_ID: 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", client.user_io.out)

        if platform.system() == "Windows":
            conan_ref = ConanFileReference.loads("lib/0.1@user/channel")
            source_folder = client.client_cache.source(conan_ref)
            build_folder = client.client_cache.build(package_ref)
            package_folder = client.client_cache.package(package_ref)
            link_source = os.path.join(source_folder, ".conan_link")
            link_build = os.path.join(build_folder, ".conan_link")
            link_package = os.path.join(package_folder, ".conan_link")

            self.assertTrue(os.path.exists(link_source))
            self.assertTrue(os.path.exists(link_build))
            self.assertTrue(os.path.exists(link_package))

    def failure_test(self):

        base = '''
from conans import ConanFile
from conans.util.files import load, save
import os

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    short_paths = True
    exports = "*"
    generators = "cmake"

    def build(self):
        self.output.info("%s/%s" % (self.build_folder, self.name))
        path = os.path.join(self.build_folder, self.name)
        # print "PATH EXISTS ", os.path.exists(path)
        # print os.listdir(path)
        path = os.path.join(path, "myfile.txt")
        # print "PATH EXISTS ", os.path.exists(path)

    def package(self):
        self.copy("*.txt", keep_path=False)
'''

        client = TestClient()
        files = {"conanfile.py": base,
                 "lib/myfile.txt": "Hello world!"}
        client.save(files)
        client.run("export . user/channel")
        client.run("install lib/0.1@user/channel --build")
        # print client.paths.store
        package_ref = PackageReference.loads("lib/0.1@user/channel:"
                                             "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_folder = client.client_cache.package(package_ref, short_paths=None)
        file1 = load(os.path.join(package_folder, "myfile.txt"))
        self.assertEqual("Hello world!", file1)

        client.run("install lib/0.1@user/channel --build")
        package_ref = PackageReference.loads("lib/0.1@user/channel:"
                                             "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_folder = client.client_cache.package(package_ref, short_paths=None)
        file1 = load(os.path.join(package_folder, "myfile.txt"))
        self.assertEqual("Hello world!", file1)
