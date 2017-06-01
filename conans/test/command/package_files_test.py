import unittest
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient
from conans.model.ref import ConanFileReference, PackageReference
from conans.util.files import load
import os
from conans.test.utils.conanfile import TestConanFile


class PackageFilesTest(unittest.TestCase):

    def test_basic(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "0.1"
    settings = "os"
"""
        client.save({CONANFILE: conanfile})
        client.run("export lasote/stable")

        client.save({"include/header.h": "//Windows header"}, clean_first=True)
        client.run("package_files Hello/0.1@lasote/stable -s os=Windows")
        conan_ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        win_package_ref = PackageReference(conan_ref, "3475bd55b91ae904ac96fde0f106a136ab951a5e")
        package_folder = client.client_cache.package(win_package_ref)
        self.assertEqual(load(os.path.join(package_folder, "include/header.h")),
                         "//Windows header")
        self._consume(client, "-s os=Windows")
        self.assertIn("Hello/0.1@lasote/stable:3475bd55b91ae904ac96fde0f106a136ab951a5e",
                      client.user_io.out)

        # Now repeat
        client.save({"include/header.h": "//Windows header2"}, clean_first=True)
        err = client.run("package_files Hello/0.1@lasote/stable -s os=Windows", ignore_error=True)
        self.assertTrue(err)
        self.assertIn("Package already exists. Please use --force, -f to overwrite it",
                      client.user_io.out)
        client.run("package_files Hello/0.1@lasote/stable -s os=Windows -f")
        self.assertEqual(load(os.path.join(package_folder, "include/header.h")),
                         "//Windows header2")

    def _consume(self, client, install_args):
        consumer = """
from conans import ConanFile
class TestConan(ConanFile):
    requires = "Hello/0.1@lasote/stable"
    settings = "os"
"""
        client.save({CONANFILE: consumer}, clean_first=True)
        client.run("install %s" % install_args)
        self.assertIn("Hello/0.1@lasote/stable: Already installed!", client.user_io.out)

    def test_new(self):
        client = TestClient()
        client.run("new Hello/0.1 --bare")
        client.run("export lasote/stable")
        client.save({"lib/libmycoollib.a": ""}, clean_first=True)
        settings = ('-s os=Windows -s compiler=gcc -s compiler.version=4.9 '
                    '-s compiler.libcxx=libstdc++ -s build_type=Release -s arch=x86')
        client.run("package_files Hello/0.1@lasote/stable %s" % settings)
        self._consume(client, settings + " -g cmake")

        cmakeinfo = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("set(CONAN_LIBS_HELLO mycoollib)", cmakeinfo)
        self.assertIn("set(CONAN_LIBS mycoollib ${CONAN_LIBS})", cmakeinfo)

    def test_paths(self):
        client = TestClient()
        client.run("new Hello/0.1 --bare")
        client.run("export lasote/stable")
        client.save({"Release_x86/lib/libmycoollib.a": ""}, clean_first=True)
        settings = ('-s os=Windows -s compiler=gcc -s compiler.version=4.9 '
                    '-s compiler.libcxx=libstdc++ -s build_type=Release -s arch=x86')
        client.run("package_files Hello/0.1@lasote/stable %s -pf=Release_x86" % settings)
        self._consume(client, settings + " -g cmake")

        cmakeinfo = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("set(CONAN_LIBS_HELLO mycoollib)", cmakeinfo)
        self.assertIn("set(CONAN_LIBS mycoollib ${CONAN_LIBS})", cmakeinfo)

    def test_with_deps(self):
        client = TestClient()
        conanfile = TestConanFile()
        client.save({"conanfile.py": str(conanfile)})
        client.run("export lasote/stable")
        client.run("install Hello/0.1@lasote/stable --build")
        conanfile = TestConanFile(name="Hello1", requires=["Hello/0.1@lasote/stable"])
        conanfile = str(conanfile) + """    def package_info(self):
        self.cpp_info.libs = self.collect_libs()
        """
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("export lasote/stable")
        client.save({"Release_x86/lib/libmycoollib.a": ""}, clean_first=True)
        settings = ('-s os=Windows -s compiler=gcc -s compiler.version=4.9 '
                    '-s compiler.libcxx=libstdc++ -s build_type=Release -s arch=x86')
        client.run("package_files Hello1/0.1@lasote/stable %s -pf=Release_x86" % settings)

        # consumer
        consumer = """
from conans import ConanFile
class TestConan(ConanFile):
    requires = "Hello1/0.1@lasote/stable"
    settings = "os"
"""
        client.save({CONANFILE: consumer}, clean_first=True)
        client.run("install -g cmake")
        self.assertIn("Hello/0.1@lasote/stable: Already installed!", client.user_io.out)
        self.assertIn("Hello1/0.1@lasote/stable: Already installed!", client.user_io.out)

        cmakeinfo = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("set(CONAN_LIBS_HELLO1 mycoollib)", cmakeinfo)
        self.assertIn("set(CONAN_LIBS mycoollib ${CONAN_LIBS})", cmakeinfo)
