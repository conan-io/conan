import unittest
import os
from conans.paths import CONANFILE
from conans.model.ref import ConanFileReference
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient
import platform


class ExportDirtyTest(unittest.TestCase):
    """ Make sure than when the source folder becomes dirty, due to a export of
    a new recipe with a rmdir failure, or to an uncomplete execution of source(),
    it is marked as dirty and removed when necessary
    """

    def setUp(self):
        if platform.system() != "Windows":
            return
        self.client = TestClient()
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)

        self.client.save(files)
        self.client.run("export . lasote/stable")
        self.client.run("install Hello0/0.1@lasote/stable --build")
        ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        source_path = self.client.paths.source(ref)
        file_open = os.path.join(source_path, "main.cpp")

        self.f = open(file_open, 'wb')
        self.f.write(b"Hello world")
        files[CONANFILE] = files[CONANFILE].replace("build2(", "build3(")
        self.client.save(files)
        self.client.run("export . lasote/stable")
        self.assertIn("ERROR: Unable to delete source folder. "
                      "Will be marked as corrupted for deletion",
                      self.client.user_io.out)

        err = self.client.run("install Hello0/0.1@lasote/stable --build", ignore_error=True)
        self.assertTrue(err)
        self.assertIn("ERROR: Unable to remove source folder", self.client.user_io.out)

    def test_export_remove(self):
        """ The export is able to remove dirty source folders
        """
        if platform.system() != "Windows":
            return
        self.f.close()
        self.client.run("export . lasote/stable")
        self.assertIn("Source folder is corrupted, forcing removal", self.client.user_io.out)
        err = self.client.run("install Hello0/0.1@lasote/stable --build")
        self.assertFalse(err)

    def test_install_remove(self):
        """ The install is also able to remove dirty source folders
        """
        if platform.system() != "Windows":
            return
        # Now, release the handle to the file
        self.f.close()
        err = self.client.run("install Hello0/0.1@lasote/stable --build")
        self.assertFalse(err)
        self.assertIn("WARN: Trying to remove corrupted source folder", self.client.user_io.out)
