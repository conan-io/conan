import os
import platform
import tempfile
import unittest

import pytest

from conans.client.tools.env import environment_append
from conans.model.ref import ConanFileReference, PackageReference
from conans.test import CONAN_TEST_FOLDER
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer
from conans.util.files import load
from textwrap import dedent

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
    @pytest.mark.skipif(platform.system() != "Windows", reason="requires Win")
    def test_failure_copy(self):
        client = TestClient()
        conanfile = dedent("""
            from conans import ConanFile
            from conans.tools import save
            import os

            class ConanLib(ConanFile):
                def source(self):
                    cwd = os.getcwd()
                    size = len(os.getcwd())
                    sub = "a/"*(int((240-size)/2))
                    path = os.path.join(cwd, sub, "file.txt")
                    path = os.path.normpath(path)
                    save(path, "contents")

            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg/1.0@user/testing", assert_error=True)
        self.assertIn("Use short_paths=True if paths too long", client.out)
        self.assertIn("Error copying sources to build folder", client.out)

    def test_remove(self):
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

    def test_upload(self):
        test_server = TestServer([],  # write permissions
                                 users={"lasote": "mypass"})  # exported users and passwords
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client.save({"conanfile.py": base})
        client.run("create . lasote/channel")
        client.run("upload lib/0.1@lasote/channel --all")
        client.run("remove lib/0.1@lasote/channel -f")
        client.run("search")
        self.assertIn("There are no packages", client.out)

        for command in ("install", "download"):
            client2 = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
            client2.run("%s lib/0.1@lasote/channel" % command)
            ref = ConanFileReference.loads("lib/0.1@lasote/channel")
            export_folder = client2.cache.package_layout(ref).export()
            export_files = os.listdir(export_folder)
            self.assertNotIn('conan_export.tgz', export_files)
            pref = PackageReference.loads("lib/0.1@lasote/channel:" + NO_SETTINGS_PACKAGE_ID)
            package_folder = client2.cache.package_layout(pref.ref).package(pref)
            if platform.system() == "Windows":
                original_folder = client2.cache.package_layout(pref.ref,
                                                               short_paths=False).package(pref)
                link = load(os.path.join(original_folder, ".conan_link"))
                self.assertEqual(link, package_folder)

            files = os.listdir(package_folder)
            self.assertIn("myfile.txt", files)
            self.assertIn("myfile2.txt", files)
            self.assertNotIn("conan_package.tgz", files)

    def test_export_source(self):
        client = TestClient()
        files = {"conanfile.py": base,
                 "path/"*20 + "file0.txt": "file0 content"}
        client.save(files)
        client.run("export . user/channel")
        ref = ConanFileReference.loads("lib/0.1@user/channel")
        source_folder = client.cache.package_layout(ref, False).export_sources()
        if platform.system() == "Windows":
            source_folder = load(os.path.join(source_folder, ".conan_link"))
        self.assertTrue(os.path.exists(source_folder))
        self.assertEqual(load(os.path.join(source_folder + "/path"*20 + "/file0.txt")),
                         "file0 content")
        client.run("install lib/0.1@user/channel --build=missing")
        pref = PackageReference.loads("lib/0.1@user/channel:%s" % NO_SETTINGS_PACKAGE_ID)
        package_folder = client.cache.package_layout(pref.ref, short_paths=False).package(pref)
        if platform.system() == "Windows":
            package_folder = load(os.path.join(package_folder, ".conan_link"))
        self.assertTrue(os.path.exists(package_folder))
        self.assertEqual(load(os.path.join(package_folder + "/file0.txt")), "file0 content")

    def test_package_copier(self):
        client = TestClient()
        files = {"conanfile.py": base}
        client.save(files)
        client.run("export . lasote/channel")
        client.run("install lib/0.1@lasote/channel --build")
        client.run("copy lib/0.1@lasote/channel memsharded/stable --all")
        client.run("search")
        self.assertIn("lib/0.1@lasote/channel", client.out)
        self.assertIn("lib/0.1@memsharded/stable", client.out)
        client.run("search lib/0.1@lasote/channel")

        self.assertIn("Package_ID: %s" % NO_SETTINGS_PACKAGE_ID, client.out)
        client.run("search lib/0.1@memsharded/stable")
        self.assertIn("Package_ID: %s" % NO_SETTINGS_PACKAGE_ID, client.out)

        ref = ConanFileReference.loads("lib/0.1@lasote/channel")
        pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID)
        package_folder = client.cache.package_layout(pref.ref, short_paths=False).package(pref)
        if platform.system() == "Windows":
            package_folder = load(os.path.join(package_folder, ".conan_link"))
        self.assertTrue(os.path.exists(package_folder))

    def test_basic(self):
        client = TestClient()
        files = {"conanfile.py": base}
        client.save(files)
        client.run("export . user/channel")
        client.run("install lib/0.1@user/channel --build")
        pref = PackageReference.loads("lib/0.1@user/channel:%s" % NO_SETTINGS_PACKAGE_ID)
        client.run("search")
        self.assertIn("lib/0.1@user/channel", client.out)
        client.run("search lib/0.1@user/channel")
        self.assertIn("Package_ID: %s" % NO_SETTINGS_PACKAGE_ID, client.out)

        package_folder = client.cache.package_layout(pref.ref, short_paths=None).package(pref)
        file1 = load(os.path.join(package_folder, "myfile.txt"))
        self.assertEqual("Hello extra path length", file1)
        file2 = load(os.path.join(package_folder, "myfile2.txt"))
        self.assertEqual("Hello2 extra path length", file2)
        if platform.system() == "Windows":
            ref = ConanFileReference.loads("lib/0.1@user/channel")
            source_folder = client.cache.package_layout(ref, False).source()
            link_source = load(os.path.join(source_folder, ".conan_link"))
            self.assertTrue(os.path.exists(link_source))

            build_folder = client.cache.package_layout(ref, False).build(pref)
            link_build = load(os.path.join(build_folder, ".conan_link"))
            self.assertTrue(os.path.exists(link_build))

            package_folder = client.cache.package_layout(ref, False).package(pref)
            link_package = load(os.path.join(package_folder, ".conan_link"))
            self.assertTrue(os.path.exists(link_package))

            client.run("remove lib* -f")
            self.assertFalse(os.path.exists(link_source))
            self.assertFalse(os.path.exists(link_build))
            self.assertFalse(os.path.exists(link_package))

    def test_basic_disabled(self):
        client = TestClient()
        conanfile = GenConanfile().with_short_paths(True)
        client.save({"conanfile.py": conanfile})

        client.run("create . lib/0.1@user/channel")
        pref = PackageReference.loads("lib/0.1@user/channel:%s" % NO_SETTINGS_PACKAGE_ID)
        client.run("search")
        self.assertIn("lib/0.1@user/channel", client.out)
        client.run("search lib/0.1@user/channel")
        self.assertIn("Package_ID: %s" % NO_SETTINGS_PACKAGE_ID, client.out)

        if platform.system() == "Windows":
            ref = ConanFileReference.loads("lib/0.1@user/channel")
            source_folder = client.cache.package_layout(ref, False).source()
            build_folder = client.cache.package_layout(ref, False).build(pref)
            package_folder = client.cache.package_layout(ref, False).package(pref)
            link_source = os.path.join(source_folder, ".conan_link")
            link_build = os.path.join(build_folder, ".conan_link")
            link_package = os.path.join(package_folder, ".conan_link")

            self.assertTrue(os.path.exists(link_source))
            self.assertTrue(os.path.exists(link_build))
            self.assertTrue(os.path.exists(link_package))

    def test_failure(self):

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
        package_folder = client.cache.package_layout(pref.ref, short_paths=None).package(pref)
        file1 = load(os.path.join(package_folder, "myfile.txt"))
        self.assertEqual("Hello world!", file1)

        client.run("install lib/0.1@user/channel --build")
        pref = PackageReference.loads("lib/0.1@user/channel:%s" % NO_SETTINGS_PACKAGE_ID)
        package_folder = client.cache.package_layout(pref.ref, short_paths=None).package(pref)
        file1 = load(os.path.join(package_folder, "myfile.txt"))
        self.assertEqual("Hello world!", file1)
