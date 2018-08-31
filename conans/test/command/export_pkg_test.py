import unittest
import platform
import os

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient, TestServer
from conans.model.ref import ConanFileReference, PackageReference
from conans.util.files import load, mkdir
from conans.test.utils.conanfile import TestConanFile
from parameterized import parameterized


class ExportPkgTest(unittest.TestCase):
    def test_dont_touch_server(self):
        # https://github.com/conan-io/conan/issues/3432
        class RequesterMock(object):
            def __init__(self, *args, **kwargs):
                pass

        # https://github.com/conan-io/conan/issues/3432
        client = TestClient(servers={"default": TestServer()},
                            requester_class=RequesterMock,
                            users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        client.run("export-pkg . Pkg/0.1@user/testing")

    def test_package_folder_errors(self):
        # https://github.com/conan-io/conan/issues/2350
        conanfile = """from conans import ConanFile
class HelloPythonConan(ConanFile):
    pass
"""
        client = TestClient()
        client.save({CONANFILE: conanfile})
        mkdir(os.path.join(client.current_folder, "pkg"))

        error = client.run("export-pkg . Hello/0.1@lasote/stable -pf=pkg -bf=.", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: package folder definition incompatible with build and source folders",
                      client.out)

        error = client.run("export-pkg . Hello/0.1@lasote/stable -pf=pkg -sf=.", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: package folder definition incompatible with build and source folders",
                      client.out)

        client.run("export-pkg . Hello/0.1@lasote/stable -pf=pkg")
        self.assertIn("Hello/0.1@lasote/stable: WARN: No files copied from package folder!",
                      client.out)

    def test_package_folder(self):
        # https://github.com/conan-io/conan/issues/2350
        conanfile = """from conans import ConanFile
class HelloPythonConan(ConanFile):
    settings = "os"
    def package(self):
        self.output.info("PACKAGE NOT CALLED")
        raise Exception("PACKAGE NOT CALLED")
"""
        client = TestClient()
        client.save({CONANFILE: conanfile,
                     "pkg/myfile.h": "",
                     "profile": "[settings]\nos=Windows"})

        client.run("export-pkg . Hello/0.1@lasote/stable -pf=pkg -pr=profile")
        self.assertNotIn("PACKAGE NOT CALLED", client.out)
        self.assertIn("Hello/0.1@lasote/stable: Copied 1 '.h' file: myfile.h", client.out)
        ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        pkg_folder = client.client_cache.packages(ref)
        folders = os.listdir(pkg_folder)
        pkg_folder = os.path.join(pkg_folder, folders[0])
        conaninfo = load(os.path.join(pkg_folder, "conaninfo.txt"))
        self.assertEqual(2, conaninfo.count("os=Windows"))
        manifest = load(os.path.join(pkg_folder, "conanmanifest.txt"))
        self.assertIn("conaninfo.txt: f395060da1ffdeb934be8b62e4bd8a3a", manifest)
        self.assertIn("myfile.h: d41d8cd98f00b204e9800998ecf8427e", manifest)

    def test_develop(self):
        # https://github.com/conan-io/conan/issues/2513
        conanfile = """from conans import ConanFile
class HelloPythonConan(ConanFile):
    def package(self):
        self.output.info("DEVELOP IS: %s!" % self.develop)
"""
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export-pkg . Hello/0.1@lasote/stable")
        self.assertIn("Hello/0.1@lasote/stable: DEVELOP IS: True!", client.out)

    def test_options(self):
        # https://github.com/conan-io/conan/issues/2242
        conanfile = """from conans import ConanFile
class HelloPythonConan(ConanFile):
    name = "Hello"
    options = { "optionOne": [True, False, 123] }
    default_options = "optionOne=True"
"""
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export-pkg . Hello/0.1@lasote/stable")
        client.run("search Hello/0.1@lasote/stable")
        self.assertIn("optionOne: True", client.out)
        self.assertNotIn("optionOne: False", client.out)
        self.assertNotIn("optionOne: 123", client.out)
        client.run("export-pkg . Hello/0.1@lasote/stable -o optionOne=False")
        client.run("search Hello/0.1@lasote/stable")
        self.assertIn("optionOne: True", client.out)
        self.assertIn("optionOne: False", client.out)
        self.assertNotIn("optionOne: 123", client.out)
        client.run("export-pkg . Hello/0.1@lasote/stable -o Hello:optionOne=123")
        client.run("search Hello/0.1@lasote/stable")
        self.assertIn("optionOne: True", client.out)
        self.assertIn("optionOne: False", client.out)
        self.assertIn("optionOne: 123", client.out)

    def test_options_install(self):
        # https://github.com/conan-io/conan/issues/2242
        conanfile = """from conans import ConanFile
class HelloPythonConan(ConanFile):
    name = "Hello"
    options = { "optionOne": [True, False, 123] }
    default_options = "optionOne=True"
"""
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("install .")
        client.run("export-pkg . Hello/0.1@lasote/stable")
        client.run("search Hello/0.1@lasote/stable")
        self.assertIn("optionOne: True", client.out)
        client.run("install . -o optionOne=False")
        client.run("export-pkg . Hello/0.1@lasote/stable")
        client.run("search Hello/0.1@lasote/stable")
        self.assertIn("optionOne: True", client.out)
        self.assertIn("optionOne: False", client.out)
        client.run("install . -o Hello:optionOne=123")
        client.run("export-pkg . Hello/0.1@lasote/stable")
        client.run("search Hello/0.1@lasote/stable")
        self.assertIn("optionOne: True", client.out)
        self.assertIn("optionOne: False", client.out)
        self.assertIn("optionOne: 123", client.out)

    @parameterized.expand([(False, ), (True, )])
    def test_basic(self, short_paths):
        client = TestClient()
        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "0.1"
    settings = "os"

    def package(self):
        self.copy("*")
"""
        if short_paths:
            conanfile += "    short_paths = True"
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        client.save({"include/header.h": "//Windows header"})
        client.run("export-pkg . Hello/0.1@lasote/stable -s os=Windows")
        conan_ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        win_package_ref = PackageReference(conan_ref, "3475bd55b91ae904ac96fde0f106a136ab951a5e")
        package_folder = client.client_cache.package(win_package_ref, short_paths=short_paths)
        if short_paths and platform.system() == "Windows":
            self.assertEqual(load(os.path.join(client.client_cache.package(win_package_ref),
                                               ".conan_link")),
                             package_folder)
        else:
            self.assertEqual(client.client_cache.package(win_package_ref), package_folder)
        self.assertEqual(load(os.path.join(package_folder, "include/header.h")),
                         "//Windows header")
        self._consume(client, ". -s os=Windows")
        self.assertIn("Hello/0.1@lasote/stable:3475bd55b91ae904ac96fde0f106a136ab951a5e",
                      client.user_io.out)

        # Now repeat
        client.save({CONANFILE: conanfile}, clean_first=True)
        client.save({"include/header.h": "//Windows header2"})
        err = client.run("export-pkg . Hello/0.1@lasote/stable -s os=Windows",
                         ignore_error=True)
        self.assertIn("Package already exists. Please use --force, -f to overwrite it",
                      client.user_io.out)
        self.assertTrue(err)

        # Will fail because it finds the info files in the curdir.
        client.run("install . -s os=Windows")
        err = client.run("export-pkg . Hello/0.1@lasote/stable -s os=Windows -f", ignore_error=True)
        self.assertTrue(err)
        self.assertIn("conaninfo.txt and conanbuildinfo.txt are found", client.out)

        client.save({CONANFILE: conanfile, "include/header.h": "//Windows header2"},
                    clean_first=True)
        client.run("export-pkg . Hello/0.1@lasote/stable -s os=Windows -f")
        self.assertEqual(load(os.path.join(package_folder, "include/header.h")),
                         "//Windows header2")

        # Now use --install-folder and avoid the -s os=Windows, should fail without  -f
        client.run("install . --install-folder=inst -s os=Windows")
        err = client.run("export-pkg . Hello/0.1@lasote/stable -if inst", ignore_error=True)
        self.assertTrue(err)
        self.assertIn("Package already exists. Please use --force, -f to overwrite it",
                      client.user_io.out)
        client.run("export-pkg . Hello/0.1@lasote/stable -if inst -f")
        self.assertEqual(load(os.path.join(package_folder, "include/header.h")),
                         "//Windows header2")

        # Try to specify a setting and the install folder
        error = client.run("export-pkg . Hello/0.1@lasote/stable -if inst -s os=Linux", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("conaninfo.txt and conanbuildinfo.txt are found", client.user_io.out)

        error = client.run("export-pkg . Hello/0.1@lasote/stable -if inst -f --profile=default",
                           ignore_error=True)
        self.assertIn("conaninfo.txt and conanbuildinfo.txt are found", client.user_io.out)
        self.assertTrue(error)

        # Try to specify a install folder with no files
        error = client.run("export-pkg . Hello/0.1@lasote/stable -if fake", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("The specified install folder doesn't contain 'conaninfo.txt' and "
                      "'conanbuildinfo.txt' files", client.user_io.out)

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
        client.save({"lib/libmycoollib.a": ""})
        settings = ('-s os=Windows -s compiler=gcc -s compiler.version=4.9 '
                    '-s compiler.libcxx=libstdc++ -s build_type=Release -s arch=x86')
        client.run("export-pkg . Hello/0.1@lasote/stable %s" % settings)
        self.assertIn("Hello/0.1@lasote/stable: A new conanfile.py version was exported",
                      client.out)
        self.assertNotIn("Hello/0.1@lasote/stable package(): WARN: No files copied",
                         client.out)  # --bare include a now mandatory package() method!

        self.assertIn("Copied 1 '.a' file: libmycoollib.a", client.out)
        self._consume(client, settings + " . -g cmake")

        cmakeinfo = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("set(CONAN_LIBS_HELLO mycoollib)", cmakeinfo)
        self.assertIn("set(CONAN_LIBS mycoollib ${CONAN_LIBS})", cmakeinfo)

        # ensure the recipe hash is computed and added
        client.run("search Hello/0.1@lasote/stable")
        self.assertIn("Outdated from recipe: False", client.user_io.out)

    def test_build_folders(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "0.1"
    settings = "os"

    def package(self):
        self.copy("*.h", src="include", dst="inc")
        self.copy("*.lib", src="lib", dst="lib")
"""
        client.save({CONANFILE: conanfile,
                     "include/header.h": "//Windows header",
                     "include/header.txt": "",
                     "libs/what": "",
                     "lib/hello.lib": "My Lib",
                     "lib/bye.txt": ""}, clean_first=True)
        client.run("export-pkg . Hello/0.1@lasote/stable -s os=Windows --build-folder=.")
        conan_ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        package_ref = PackageReference(conan_ref, "3475bd55b91ae904ac96fde0f106a136ab951a5e")
        package_folder = client.client_cache.package(package_ref)
        inc = os.path.join(package_folder, "inc")
        self.assertEqual(os.listdir(inc), ["header.h"])
        self.assertEqual(load(os.path.join(inc, "header.h")), "//Windows header")
        lib = os.path.join(package_folder, "lib")
        self.assertEqual(os.listdir(lib), ["hello.lib"])
        self.assertEqual(load(os.path.join(lib, "hello.lib")), "My Lib")

    def test_default_source_folder(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class TestConan(ConanFile):

    def package(self):
        self.copy("*.h", src="src", dst="include")
        self.copy("*.lib", dst="lib", keep_path=False)
"""
        client.save({CONANFILE: conanfile,
                     "src/header.h": "contents",
                     "build/lib/hello.lib": "My Lib"})
        client.run("export-pkg . Hello/0.1@lasote/stable -s os=Windows --build-folder=build")
        conan_ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        package_ref = PackageReference(conan_ref, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_folder = client.client_cache.package(package_ref)
        header = os.path.join(package_folder, "include/header.h")
        self.assertTrue(os.path.exists(header))

        hello_path = os.path.join(package_folder, "lib", "hello.lib")
        self.assertTrue(os.path.exists(hello_path))

    def test_build_source_folders(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class TestConan(ConanFile):
    settings = "os"

    def package(self):
        self.copy("*.h", src="include", dst="inc")
        self.copy("*.lib", src="lib", dst="lib")
"""
        client.save({CONANFILE: conanfile,
                     "src/include/header.h": "//Windows header",
                     "src/include/header.txt": "",
                     "build/libs/what": "",
                     "build/lib/hello.lib": "My Lib",
                     "build/lib/bye.txt": ""})
        client.run("export-pkg . Hello/0.1@lasote/stable -s os=Windows --build-folder=build "
                   "--source-folder=src")
        conan_ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        package_ref = PackageReference(conan_ref, "3475bd55b91ae904ac96fde0f106a136ab951a5e")
        package_folder = client.client_cache.package(package_ref)
        inc = os.path.join(package_folder, "inc")
        self.assertEqual(os.listdir(inc), ["header.h"])
        self.assertEqual(load(os.path.join(inc, "header.h")), "//Windows header")
        lib = os.path.join(package_folder, "lib")
        self.assertEqual(os.listdir(lib), ["hello.lib"])
        self.assertEqual(load(os.path.join(lib, "hello.lib")), "My Lib")

    def test_partial_references(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "0.1"
    settings = "os"

    def package(self):
        self.copy("*")
"""
        # Partial reference is ok
        client.save({CONANFILE: conanfile, "file.txt": "txt contents"})
        client.run("export-pkg . conan/stable")
        self.assertIn("Hello/0.1@conan/stable package(): Copied 1 '.txt' file: file.txt", client.out)

        # Specify different name or version is not working
        error = client.run("export-pkg . lib/1.0@conan/stable -f", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Package recipe exported with name lib!=Hello", client.out)

        error = client.run("export-pkg . Hello/1.1@conan/stable -f", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Package recipe exported with version 1.1!=0.1", client.out)

        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    settings = "os"

    def package(self):
        self.copy("*")
"""
        # Partial reference is ok
        client.save({CONANFILE: conanfile, "file.txt": "txt contents"})
        client.run("export-pkg . anyname/1.222@conan/stable")
        self.assertIn("anyname/1.222@conan/stable package(): Copied 1 '.txt' file: file.txt", client.out)

    def test_with_deps(self):
        client = TestClient()
        conanfile = TestConanFile()
        client.save({"conanfile.py": str(conanfile)})
        client.run("export . lasote/stable")
        client.run("install Hello/0.1@lasote/stable --build")
        conanfile = TestConanFile(name="Hello1", requires=["Hello/0.1@lasote/stable"])
        conanfile = str(conanfile) + """    def package_info(self):
        self.cpp_info.libs = self.collect_libs()
    def package(self):
        self.copy("*")
        """
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.save({"Release_x86/lib/libmycoollib.a": ""})
        settings = ('-s os=Windows -s compiler=gcc -s compiler.version=4.9 '
                    '-s compiler.libcxx=libstdc++ -s build_type=Release -s arch=x86')
        client.run("export-pkg . Hello1/0.1@lasote/stable %s -bf=Release_x86" % settings)

        # consumer
        consumer = """
from conans import ConanFile
class TestConan(ConanFile):
    requires = "Hello1/0.1@lasote/stable"
    settings = "os"
"""
        client.save({CONANFILE: consumer}, clean_first=True)
        client.run("install conanfile.py -g cmake")
        self.assertIn("Hello/0.1@lasote/stable: Already installed!", client.user_io.out)
        self.assertIn("Hello1/0.1@lasote/stable: Already installed!", client.user_io.out)

        cmakeinfo = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("set(CONAN_LIBS_HELLO1 mycoollib)", cmakeinfo)
        self.assertIn("set(CONAN_LIBS mycoollib ${CONAN_LIBS})", cmakeinfo)
