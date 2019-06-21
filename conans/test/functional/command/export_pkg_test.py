import json
import os
import platform
import unittest
from textwrap import dedent

from parameterized import parameterized

from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE
from conans.test.utils.conanfile import TestConanFile
from conans.test.utils.deprecation import catch_deprecation_warning
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient
from conans.util.env_reader import get_env
from conans.util.files import load, mkdir


class ExportPkgTest(unittest.TestCase):

    def test_dont_touch_server(self):
        # https://github.com/conan-io/conan/issues/3432
        client = TestClient(servers={"default": None},
                            requester_class=None,
                            users={"default": [("lasote", "mypass")]})

        client.save({"conanfile.py": str(TestConanFile("Pkg", "0.1"))})
        client.run("install .")
        client.run("export-pkg . Pkg/0.1@user/testing")

    def test_dont_touch_server_build_require(self):
        client = TestClient(servers={"default": None},
                            requester_class=None,
                            users={"default": [("lasote", "mypass")]})
        profile = dedent("""
            [build_requires]
            some/other@pkg/notexists
            """)
        client.save({"conanfile.py": str(TestConanFile("Pkg", "0.1")),
                     "myprofile": profile})
        client.run("export-pkg . Pkg/0.1@user/testing -pr=myprofile")

    def test_transitive_without_settings(self):
        # https://github.com/conan-io/conan/issues/3367
        conanfile = """from conans import ConanFile
class PkgC(ConanFile):
    pass
"""
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("create . PkgC/0.1@user/testing")
        conanfile = """from conans import ConanFile
class PkgB(ConanFile):
    settings = "arch"
    requires = "PkgC/0.1@user/testing"
"""
        client.save({CONANFILE: conanfile})
        client.run("create . PkgB/0.1@user/testing")
        conanfile = """from conans import ConanFile
class PkgA(ConanFile):
    requires = "PkgB/0.1@user/testing"
    def build(self):
        self.output.info("BUILDING PKGA")
"""
        client.save({CONANFILE: conanfile})
        client.run("install . -if=build")
        client.run("build . -bf=build")
        with catch_deprecation_warning(self, n=2):
            client.run("export-pkg . PkgA/0.1@user/testing -bf=build -pr=default")
        self.assertIn("PkgA/0.1@user/testing: Package "
                      "'8f97510bcea8206c1c046cc8d71cc395d4146547' created",
                      client.out)

    def test_package_folder_errors(self):
        # https://github.com/conan-io/conan/issues/2350
        conanfile = """from conans import ConanFile
class HelloPythonConan(ConanFile):
    pass
"""
        client = TestClient()
        client.save({CONANFILE: conanfile})
        mkdir(os.path.join(client.current_folder, "pkg"))

        client.run("export-pkg . Hello/0.1@lasote/stable -pf=pkg -bf=.", assert_error=True)
        self.assertIn("ERROR: package folder definition incompatible with build and source folders",
                      client.out)

        client.run("export-pkg . Hello/0.1@lasote/stable -pf=pkg -sf=.", assert_error=True)
        self.assertIn("ERROR: package folder definition incompatible with build and source folders",
                      client.out)

        client.run("export-pkg . Hello/0.1@lasote/stable -pf=pkg")
        self.assertIn("Hello/0.1@lasote/stable: WARN: No files in this package!",
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
        self.assertIn("Hello/0.1@lasote/stable: Packaged 1 '.h' file: myfile.h", client.out)
        self.assertNotIn("No files in this package!", client.out)
        ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        pkg_folder = client.cache.package_layout(ref).packages()
        folders = os.listdir(pkg_folder)
        pkg_folder = os.path.join(pkg_folder, folders[0])
        conaninfo = load(os.path.join(pkg_folder, "conaninfo.txt"))
        self.assertEqual(2, conaninfo.count("os=Windows"))
        manifest = load(os.path.join(pkg_folder, "conanmanifest.txt"))
        self.assertIn("conaninfo.txt: d5fc27fb8ecb98697c94f6209b44531f", manifest)
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

    def test_profile_environment(self):
        # https://github.com/conan-io/conan/issues/4832
        conanfile = dedent("""
            import os
            from conans import ConanFile
            class HelloPythonConan(ConanFile):
                def package(self):
                    self.output.info("ENV-VALUE: %s!!!" % os.getenv("MYCUSTOMVAR"))
            """)
        profile = dedent("""
            [env]
            MYCUSTOMVAR=MYCUSTOMVALUE
            """)
        client = TestClient()
        client.save({CONANFILE: conanfile,
                     "myprofile": profile})
        client.run("export-pkg . Hello/0.1@lasote/stable -pr=myprofile")
        self.assertIn("Hello/0.1@lasote/stable: ENV-VALUE: MYCUSTOMVALUE!!!", client.out)

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
    @unittest.skipIf(get_env("TESTING_REVISIONS_ENABLED", False),
                     "This test exports several RREVS assuming that the "
                     "packages will be preserved and they will be removed")
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
        ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        win_pref = PackageReference(ref, "3475bd55b91ae904ac96fde0f106a136ab951a5e")
        package_folder = client.cache.package_layout(win_pref.ref,
                                                     short_paths=short_paths).package(win_pref)
        if short_paths and platform.system() == "Windows":
            self.assertEqual(load(os.path.join(client.cache.package_layout(win_pref.ref, False).package(win_pref),
                                               ".conan_link")),
                             package_folder)
        else:
            self.assertEqual(client.cache.package_layout(win_pref.ref).package(win_pref),
                             package_folder)
        self.assertEqual(load(os.path.join(package_folder, "include/header.h")),
                         "//Windows header")
        self._consume(client, ". -s os=Windows")
        self.assertIn("Hello/0.1@lasote/stable:3475bd55b91ae904ac96fde0f106a136ab951a5e",
                      client.user_io.out)

        # Now repeat
        client.save({CONANFILE: conanfile,
                     "include/header.h": "//Windows header2"}, clean_first=True)
        # Without force it fails
        err = client.run("export-pkg . Hello/0.1@lasote/stable -s os=Windows",
                         assert_error=True)
        self.assertIn("Package already exists. Please use --force, -f to overwrite it",
                      client.user_io.out)
        self.assertTrue(err)
        # With force works
        client.run("export-pkg . Hello/0.1@lasote/stable -s os=Windows -f")
        self.assertEqual(load(os.path.join(package_folder, "include/header.h")),
                         "//Windows header2")

        # Now use --install-folder
        client.save({CONANFILE: conanfile,
                     "include/header.h": "//Windows header3"}, clean_first=True)
        # Without force it fails
        client.run("install . --install-folder=inst -s os=Windows")
        err = client.run("export-pkg . Hello/0.1@lasote/stable -if inst", assert_error=True)
        self.assertTrue(err)
        self.assertIn("Package already exists. Please use --force, -f to overwrite it",
                      client.user_io.out)
        # With force works
        client.run("export-pkg . Hello/0.1@lasote/stable -if inst -f")
        self.assertIn("Hello/0.1@lasote/stable: Package '3475bd55b91ae904ac96fde0f106a136ab951a5e'"
                      " created", client.out)
        self.assertEqual(load(os.path.join(package_folder, "include/header.h")),
                         "//Windows header3")

        # we can specify settings too
        client.save({"include/header.h": "//Windows header4"})
        client.run("export-pkg . Hello/0.1@lasote/stable -if inst -f -s os=Windows")
        self.assertIn("Hello/0.1@lasote/stable: Package '3475bd55b91ae904ac96fde0f106a136ab951a5e'"
                      " created", client.out)
        self.assertEqual(load(os.path.join(package_folder, "include/header.h")),
                         "//Windows header4")

        # Try to specify a install folder with no files
        client.run("export-pkg . Hello/0.1@lasote/stable -if fake", assert_error=True)
        self.assertIn("ERROR: Failed to load graphinfo file in install-folder", client.out)

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
        self.assertNotIn("Hello/0.1@lasote/stable package(): WARN: No files in this package!",
                         client.out)  # --bare include a now mandatory package() method!

        self.assertIn("Packaged 1 '.a' file: libmycoollib.a", client.out)
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
        ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        pref = PackageReference(ref, "3475bd55b91ae904ac96fde0f106a136ab951a5e")
        package_folder = client.cache.package_layout(pref.ref).package(pref)
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
        ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID)
        package_folder = client.cache.package_layout(pref.ref).package(pref)
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
        ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        pref = PackageReference(ref, "3475bd55b91ae904ac96fde0f106a136ab951a5e")
        package_folder = client.cache.package_layout(pref.ref).package(pref)
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
        self.assertIn("Hello/0.1@conan/stable package(): Packaged 1 '.txt' file: file.txt",
                      client.out)

        # Specify different name or version is not working
        client.run("export-pkg . lib/1.0@conan/stable -f", assert_error=True)
        self.assertIn("ERROR: Package recipe exported with name lib!=Hello", client.out)

        client.run("export-pkg . Hello/1.1@conan/stable -f", assert_error=True)
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
        self.assertIn("anyname/1.222@conan/stable package(): Packaged 1 '.txt' file: file.txt",
                      client.out)

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

    def export_pkg_json_test(self):

        def _check_json_output(with_error=False):
            json_path = os.path.join(self.client.current_folder, "output.json")
            self.assertTrue(os.path.exists(json_path))
            json_content = load(json_path)
            output = json.loads(json_content)
            self.assertEqual(output["error"], with_error)
            tmp = ConanFileReference.loads(output["installed"][0]["recipe"]["id"])
            if self.client.cache.config.revisions_enabled:
                self.assertIsNotNone(tmp.revision)
            self.assertEqual(str(tmp), "mypackage/0.1.0@danimtb/testing")
            self.assertFalse(output["installed"][0]["recipe"]["dependency"])
            self.assertTrue(output["installed"][0]["recipe"]["exported"])
            if with_error:
                self.assertEqual(output["installed"][0]["packages"], [])
            else:
                self.assertEqual(output["installed"][0]["packages"][0]["id"],
                                 NO_SETTINGS_PACKAGE_ID)
                self.assertTrue(output["installed"][0]["packages"][0]["exported"])

        conanfile = """from conans import ConanFile
class MyConan(ConanFile):
    name = "mypackage"
    version = "0.1.0"
"""
        self.client = TestClient()
        self.client.save({"conanfile.py": conanfile})

        # Wrong folders
        self.client.run("export-pkg . danimtb/testing -bf build -sf sources "
                        "--json output.json", assert_error=True)

        _check_json_output(with_error=True)

        # Deafult folders
        self.client.run("export-pkg . danimtb/testing --json output.json --force")
        _check_json_output()

        # Without package_folder
        self.client.save({"sources/kk.cpp": "", "build/kk.lib": ""})
        self.client.run("export-pkg . danimtb/testing -bf build -sf sources --json output.json "
                        "--force")
        _check_json_output()

        # With package_folder
        self.client.save({"package/kk.lib": ""})
        self.client.run("export-pkg . danimtb/testing -pf package --json output.json --force")
        _check_json_output()

    def json_with_dependencies_test(self):

        def _check_json_output(with_error=False):
            json_path = os.path.join(self.client.current_folder, "output.json")
            self.assertTrue(os.path.exists(json_path))
            json_content = load(json_path)
            output = json.loads(json_content)
            self.assertEqual(output["error"], with_error)
            tmp = ConanFileReference.loads(output["installed"][0]["recipe"]["id"])
            if self.client.cache.config.revisions_enabled:
                self.assertIsNotNone(tmp.revision)
            self.assertEqual(str(tmp), "pkg2/1.0@danimtb/testing")
            self.assertFalse(output["installed"][0]["recipe"]["dependency"])
            self.assertTrue(output["installed"][0]["recipe"]["exported"])
            if with_error:
                self.assertEqual(output["installed"][0]["packages"], [])
            else:
                self.assertEqual(output["installed"][0]["packages"][0]["id"],
                                 "5825778de2dc9312952d865df314547576f129b3")
                self.assertTrue(output["installed"][0]["packages"][0]["exported"])
                tmp = ConanFileReference.loads(output["installed"][1]["recipe"]["id"])
                if self.client.cache.config.revisions_enabled:
                    self.assertIsNotNone(tmp.revision)
                self.assertEqual(str(tmp), "pkg1/1.0@danimtb/testing")
                self.assertTrue(output["installed"][1]["recipe"]["dependency"])

        conanfile = """from conans import ConanFile
class MyConan(ConanFile):
    pass
"""
        self.client = TestClient()
        self.client.save({"conanfile_dep.py": conanfile,
                          "conanfile.py": conanfile + "    requires = \"pkg1/1.0@danimtb/testing\""})
        self.client.run("export conanfile_dep.py pkg1/1.0@danimtb/testing")
        self.client.run("export-pkg conanfile.py pkg2/1.0@danimtb/testing --json output.json")
        _check_json_output()

        # Error on missing dependency
        self.client.run("remove pkg1/1.0@danimtb/testing --force")
        self.client.run("remove pkg2/1.0@danimtb/testing --force")
        self.client.run("export-pkg conanfile.py pkg2/1.0@danimtb/testing --json output.json",
                        assert_error=True)
        _check_json_output(with_error=True)
