import os
import platform
import tempfile
import unittest

from conans.client.tools.env import environment_append
from conans.model.ref import ConanFileReference, PackageReference
from conans.test import CONAN_TEST_FOLDER
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer
from conans.util.files import load

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
            ref = ConanFileReference.loads("lib/0.1@lasote/channel")
            export_folder = client2.cache.export(ref)
            export_files = os.listdir(export_folder)
            self.assertNotIn('conan_export.tgz', export_files)
            pref = PackageReference.loads("lib/0.1@lasote/channel:" + NO_SETTINGS_PACKAGE_ID)
            package_folder = client2.cache.package(pref, short_paths=None)
            if platform.system() == "Windows":
                original_folder = client2.cache.package(pref)
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
        ref = ConanFileReference.loads("lib/0.1@user/channel")
        source_folder = client.cache.export_sources(ref)
        if platform.system() == "Windows":
            source_folder = load(os.path.join(source_folder, ".conan_link"))
        self.assertTrue(os.path.exists(source_folder))
        self.assertEqual(load(os.path.join(source_folder + "/path"*20 + "/file0.txt")),
                         "file0 content")
        client.run("install lib/0.1@user/channel --build=missing")
        pref = PackageReference.loads("lib/0.1@user/channel:%s" % NO_SETTINGS_PACKAGE_ID)
        package_folder = client.cache.package(pref)
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

        self.assertIn("Package_ID: %s" % NO_SETTINGS_PACKAGE_ID, client.user_io.out)
        client.run("search lib/0.1@memsharded/stable")
        self.assertIn("Package_ID: %s" % NO_SETTINGS_PACKAGE_ID, client.user_io.out)

        ref = ConanFileReference.loads("lib/0.1@lasote/channel")
        pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID)
        package_folder = client.cache.package(pref)
        if platform.system() == "Windows":
            package_folder = load(os.path.join(package_folder, ".conan_link"))
        self.assertTrue(os.path.exists(package_folder))

    def basic_test(self):
        client = TestClient()
        files = {"conanfile.py": base}
        client.save(files)
        client.run("export . user/channel")
        client.run("install lib/0.1@user/channel --build")
        pref = PackageReference.loads("lib/0.1@user/channel:%s" % NO_SETTINGS_PACKAGE_ID)
        client.run("search")
        self.assertIn("lib/0.1@user/channel", client.user_io.out)
        client.run("search lib/0.1@user/channel")
        self.assertIn("Package_ID: %s" % NO_SETTINGS_PACKAGE_ID, client.user_io.out)

        package_folder = client.cache.package(pref, short_paths=None)
        file1 = load(os.path.join(package_folder, "myfile.txt"))
        self.assertEqual("Hello extra path length", file1)
        file2 = load(os.path.join(package_folder, "myfile2.txt"))
        self.assertEqual("Hello2 extra path length", file2)
        if platform.system() == "Windows":
            ref = ConanFileReference.loads("lib/0.1@user/channel")
            source_folder = client.cache.source(ref)
            link_source = load(os.path.join(source_folder, ".conan_link"))
            self.assertTrue(os.path.exists(link_source))

            build_folder = client.cache.build(pref)
            link_build = load(os.path.join(build_folder, ".conan_link"))
            self.assertTrue(os.path.exists(link_build))

            package_folder = client.cache.package(pref)
            link_package = load(os.path.join(package_folder, ".conan_link"))
            self.assertTrue(os.path.exists(link_package))

            client.run("remove lib* -f")
            self.assertFalse(os.path.exists(link_source))
            self.assertFalse(os.path.exists(link_build))
            self.assertFalse(os.path.exists(link_package))

    def basic_disabled_test(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class ConanLib(ConanFile):
    short_paths = True
'''
        client.save({"conanfile.py": conanfile})

        client.run("create . lib/0.1@user/channel")
        pref = PackageReference.loads("lib/0.1@user/channel:%s" % NO_SETTINGS_PACKAGE_ID)
        client.run("search")
        self.assertIn("lib/0.1@user/channel", client.user_io.out)
        client.run("search lib/0.1@user/channel")
        self.assertIn("Package_ID: %s" % NO_SETTINGS_PACKAGE_ID, client.user_io.out)

        if platform.system() == "Windows":
            ref = ConanFileReference.loads("lib/0.1@user/channel")
            source_folder = client.cache.source(ref)
            build_folder = client.cache.build(pref)
            package_folder = client.cache.package(pref)
            link_source = os.path.join(source_folder, ".conan_link")
            link_build = os.path.join(build_folder, ".conan_link")
            link_package = os.path.join(package_folder, ".conan_link")

            self.assertTrue(os.path.exists(link_source))
            self.assertTrue(os.path.exists(link_build))
            self.assertTrue(os.path.exists(link_package))

    def failure_test(self):

        conanfile = '''
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
        files = {"conanfile.py": conanfile,
                 "lib/myfile.txt": "Hello world!"}
        client.save(files)
        client.run("export . user/channel")
        client.run("install lib/0.1@user/channel --build")
        # print client.paths.store
        pref = PackageReference.loads("lib/0.1@user/channel:%s" % NO_SETTINGS_PACKAGE_ID)
        package_folder = client.cache.package(pref, short_paths=None)
        file1 = load(os.path.join(package_folder, "myfile.txt"))
        self.assertEqual("Hello world!", file1)

        client.run("install lib/0.1@user/channel --build")
        pref = PackageReference.loads("lib/0.1@user/channel:%s" % NO_SETTINGS_PACKAGE_ID)
        package_folder = client.cache.package(pref, short_paths=None)
        file1 = load(os.path.join(package_folder, "myfile.txt"))
        self.assertEqual("Hello world!", file1)
