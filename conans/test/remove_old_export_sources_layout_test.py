import unittest
import os

from conans.paths import EXPORT_SOURCES_DIR_OLD
from conans.util.files import tar_extract
from conans.test.utils.tools import TestServer, TestClient
from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder


class DoNotKeepOldExportSourcesLayoutTest(unittest.TestCase):

    def test_basic(self):
        """ check that we do not generate anymore tgz with .c_src.
        also, they are not present any more in the cache layout, even if they come from a .c_src
        tgz server file
        """
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    name= "Pkg"
    version = "0.1"
    exports_sources = "*.txt"
""", "myfile.txt": "Hello world"})
        client.run("export . lasote/testing")
        client.run("upload Pkg/0.1@lasote/testing")
        client.run("remove * -f")
        client.run("search")
        self.assertIn("There are no packages", client.user_io.out)
        conan_reference = ConanFileReference.loads("Pkg/0.1@lasote/testing")
        path = test_server.paths.export(conan_reference)
        sources_tgz = os.path.join(path, "conan_sources.tgz")
        self.assertTrue(os.path.exists(sources_tgz))
        folder = temp_folder()
        with open(sources_tgz, 'rb') as file_handler:
            tar_extract(file_handler, folder)
        self.assertEqual(os.listdir(folder), ["myfile.txt"])
        # Now install again
        client.run("install Pkg/0.1@lasote/testing --build=missing")
        export = client.client_cache.export(conan_reference)
        self.assertNotIn(EXPORT_SOURCES_DIR_OLD, os.listdir(export))
        export_sources = client.client_cache.export_sources(conan_reference)
        self.assertEqual(os.listdir(export_sources), ["myfile.txt"])
