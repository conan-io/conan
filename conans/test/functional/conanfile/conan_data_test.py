import os
import unittest

from bottle import static_file
from nose.plugins.attrib import attr

from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import tgz_with_contents
from conans.test.utils.tools import TestClient, StoppableThreadBottle


class ConanDataTest(unittest.TestCase):

    def conan_exports_kept_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile

class Lib(ConanFile):
    exports = "myfile.txt"
"""
        client.save({"conanfile.py": conanfile,
                     "myfile.txt": "bar",
                     "conandata.yml": """
foo:
  bar: "as"                   
"""})
        ref = ConanFileReference.loads("Lib/0.1@user/testing")
        client.run("export . {}".format(ref))
        export_folder = client.cache.package_layout(ref).export()
        self.assertTrue(os.path.exists(os.path.join(export_folder, "conandata.yml")))
        self.assertTrue(os.path.exists(os.path.join(export_folder, "myfile.txt")))

    def conan_data_everywhere_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile

class Lib(ConanFile):

    def _assert_data(self):
        assert(self.conan_data["sources"]["all"]["url"] == "the url")
        assert(self.conan_data["sources"]["all"]["other"] == "field")
        self.output.info("My URL: {}".format(self.conan_data["sources"]["all"]["url"]))

    def configure(self):
        self._assert_data()

    def config_options(self):
        self._assert_data()

    def source(self):
        self._assert_data()

    def build(self):
        self._assert_data()
        
    def package(self):
        self._assert_data()

    def package_info(self):
        self._assert_data()
"""
        client.save({"conanfile.py": conanfile,
                     "conandata.yml": """
sources:
  all:
    url: "the url"
    other: "field"                   
"""})
        ref = ConanFileReference.loads("Lib/0.1@user/testing")
        client.run("create . {}".format(ref))
        self.assertIn("File 'conandata.yml' found. Exporting it...", client.out)
        self.assertIn("My URL:", client.out)
        export_folder = client.cache.package_layout(ref).export()
        self.assertTrue(os.path.exists(os.path.join(export_folder, "conandata.yml")))

        # Transitive loaded?
        client.save({"conanfile.txt": "[requires]\n{}".format(ref)}, clean_first=True)
        client.run("install . ")
        self.assertIn("My URL:", client.out)
        client.run("install . --build")
        self.assertIn("My URL:", client.out)

    @attr("slow")
    def conan_data_as_source_test(self):

        tgz_path = tgz_with_contents({"foo.txt": "bar"})

        # Instance stoppable thread server and add endpoints
        thread = StoppableThreadBottle()

        @thread.server.get("/myfile.tar.gz")
        def get_file():
            return static_file(os.path.basename(tgz_path), root=os.path.dirname(tgz_path))

        thread.run_server()

        client = TestClient()
        conanfile = """
from conans import ConanFile, tools

class Lib(ConanFile):
 
    def source(self):
        tools.get(**self.conan_data["sources"]["all"])
        self.output.info("OK!")
"""
        client.save({"conanfile.py": conanfile,
                     "conandata.yml": """
sources:
  all:
    url: "http://localhost:{}/myfile.tar.gz"
    md5: "530e88952844f62f4b322ca13191062e"
    sha1: "fae807733fcc7d1f22354755d468b748ab972a4d"
    sha256: "8ac04f26347c82b2305dd3beb9c24d81e275f5c30cd4840f94cf31dfa8eaf381"                   
""".format(thread.port)})
        ref = ConanFileReference.loads("Lib/0.1@user/testing")
        client.run("create . {}".format(ref))
        self.assertIn("OK!", client.out)

        source_folder = client.cache.package_layout(ref).source()
        self.assertTrue(os.path.exists(os.path.join(source_folder, "foo.txt")))

    def invalid_yml_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile

class Lib(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile,
                     "conandata.yml": ">>>> ::"})
        ref = ConanFileReference.loads("Lib/0.1@user/testing")
        client.run("create . {}".format(ref), assert_error=True)
        self.assertIn("ERROR: Error loading conanfile at", client.out)
        self.assertIn(": Invalid yml format at conandata.yml: while scanning a block scalar", client.out)
