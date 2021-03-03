import os
import platform
import textwrap
import unittest

import pytest

from conans.model.ref import ConanFileReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import load


class SourceDirtyTest(unittest.TestCase):
    def test_keep_failing_source_folder(self):
        # https://github.com/conan-io/conan/issues/4025
        client = TestClient()
        conanfile = textwrap.dedent("""\
            from conans import ConanFile
            from conans.tools import save
            class Pkg(ConanFile):
                def source(self):
                    save("somefile.txt", "hello world!!!")
                    raise Exception("boom")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg/1.0@user/channel", assert_error=True)
        self.assertIn("ERROR: pkg/1.0@user/channel: Error in source() method, line 6", client.out)
        ref = ConanFileReference.loads("pkg/1.0@user/channel")
        # Check that we can debug and see the folder
        self.assertEqual(load(os.path.join(client.cache.package_layout(ref).source(),
                                           "somefile.txt")),
                         "hello world!!!")
        client.run("create . pkg/1.0@user/channel", assert_error=True)
        self.assertIn("pkg/1.0@user/channel: Source folder is corrupted, forcing removal",
                      client.out)
        client.save({"conanfile.py": conanfile.replace("source(", "source2(")})
        client.run("create . pkg/1.0@user/channel")
        self.assertIn("pkg/1.0@user/channel: Source folder is corrupted, forcing removal",
                      client.out)
        # Check that it is empty
        self.assertEqual(os.listdir(os.path.join(client.cache.package_layout(ref).source())), [])


@pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows for rmdir block")
class ExportDirtyTest(unittest.TestCase):
    """ Make sure than when the source folder becomes dirty, due to a export of
    a new recipe with a rmdir failure, or to an uncomplete execution of source(),
    it is marked as dirty and removed when necessary
    """

    def setUp(self):
        self.client = TestClient()
        self.client.save({"conanfile.py": GenConanfile().with_exports("main.cpp"),
                          "main.cpp": ""})
        self.client.run("create . pkg/0.1@user/stable")
        ref = ConanFileReference.loads("pkg/0.1@user/stable")
        source_path = self.client.cache.package_layout(ref).source()
        file_open = os.path.join(source_path, "main.cpp")

        self.f = open(file_open, 'wb')
        self.f.write(b"Hello world")

        self.client.save({"conanfile.py": GenConanfile().with_exports("main.cpp", "other.h"),
                          "main.cpp": ""})
        self.client.run("export . pkg/0.1@user/stable")
        self.assertIn("ERROR: Unable to delete source folder. "
                      "Will be marked as corrupted for deletion",
                      self.client.out)

        self.client.run("install pkg/0.1@user/stable --build", assert_error=True)
        self.assertIn("ERROR: Unable to remove source folder", self.client.out)

    def test_export_remove(self):
        # export is able to remove dirty source folders
        self.f.close()
        self.client.run("export . pkg/0.1@user/stable")
        self.assertIn("Source folder is corrupted, forcing removal", self.client.out)
        self.client.run("install pkg/0.1@user/stable --build")
        self.assertNotIn("WARN: Trying to remove corrupted source folder", self.client.out)

    def test_install_remove(self):
        # install is also able to remove dirty source folders
        # Now, release the handle to the file
        self.f.close()
        self.client.run("install pkg/0.1@user/stable --build")
        self.assertIn("WARN: Trying to remove corrupted source folder", self.client.out)
