import unittest
import os
from conans.test.tools import TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.util.files import save
from conans.client.short_paths_conf import SHORTED_REFERENCES_FILENAME
from conans.test.utils.test_files import temp_folder


class ConanShortPathReferencesTest(unittest.TestCase):

    def use_short_paths_test(self):
        client = TestClient()
        shorted_path = temp_folder()
        short_paths_refs_file = os.path.join(client.paths.conan_folder,
                                             SHORTED_REFERENCES_FILENAME)
        save(short_paths_refs_file, "Hello0/0.1@lasote/stable: %s" % shorted_path)
        files = cpp_hello_conan_files("Hello0", "0.1")
        client.save(files, clean_first=True)
        client.run("export lasote/stable")
        self.assertTrue(os.path.exists(os.path.join(shorted_path, "e")))
        self.assertFalse(os.path.exists(os.path.join(shorted_path, "p")))
        self.assertFalse(os.path.exists(os.path.join(shorted_path, "b")))

        client.run("install Hello0/0.1@lasote/stable --build")
        self.assertTrue(os.path.exists(os.path.join(shorted_path, "p")))
        self.assertTrue(os.path.exists(os.path.join(shorted_path, "b")))

        sha_short = os.listdir(os.path.join(os.path.join(shorted_path, "p")))[0]
        self.assertEquals(len(sha_short), 6)
        self.assertTrue(os.path.exists(os.path.join(shorted_path, "p", sha_short, "lib")))

        client.run("search Hello0*")
        self.assertIn("Hello0/0.1@lasote/stable", str(client.user_io.out))
