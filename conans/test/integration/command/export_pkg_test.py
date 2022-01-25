import json
import os
import re

import textwrap
import unittest
from textwrap import dedent

import pytest

from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.paths import CONANFILE
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, GenConanfile
from conans.util.files import load, is_dirty


class ExportPkgTest(unittest.TestCase):

    def test_dont_touch_server(self):
        # https://github.com/conan-io/conan/issues/3432
        client = TestClient(servers={"default": None},
                            requester_class=None, inputs=["admin", "password"])

        client.save({"conanfile.py": GenConanfile().with_name("pkg").with_version("0.1")})
        client.run("install .")
        client.run("export-pkg . --user=lasote --channel=stable ")

    @pytest.mark.xfail(reason="Build-requires are expanded now, so this is expected to fail atm")
    def test_dont_touch_server_build_require(self):
        client = TestClient(servers={"default": None},
                            requester_class=None, inputs=["admin", "password"])
        profile = dedent("""
            [tool_requires]
            some/other@pkg/notexists
            """)
        client.save({"conanfile.py": GenConanfile(),
                     "myprofile": profile})
        client.run("export-pkg . --name=pkg --version=0.1 --user=user --channel=testing -pr=myprofile")

    def test_transitive_without_settings(self):
        # https://github.com/conan-io/conan/issues/3367
        client = TestClient()
        client.save({CONANFILE: GenConanfile()})
        client.run("create . --name=pkgc --version=0.1 --user=user --channel=testing")
        conanfile = """from conans import ConanFile
class PkgB(ConanFile):
    settings = "arch"
    requires = "pkgc/0.1@user/testing"
"""
        client.save({CONANFILE: conanfile})
        client.run("create . --name=pkgb --version=0.1 --user=user --channel=testing")
        conanfile = """from conans import ConanFile
class PkgA(ConanFile):
    requires = "pkgb/0.1@user/testing"
    def build(self):
        self.output.info("BUILDING PKGA")
"""
        client.save({CONANFILE: conanfile})
        client.run("install . -if=build")
        client.run("build . -bf=build")
        client.run("export-pkg . --name=pkga --version=0.1 --user=user --channel=testing "
                   "-pr=default")
        package_id = re.search(r"Packaging to (\S+)", str(client.out)).group(1)
        self.assertIn(f"pkga/0.1@user/testing: Package '{package_id}' created", client.out)

    def test_package_folder_errors(self):
        # https://github.com/conan-io/conan/issues/2350
        client = TestClient()
        client.save({CONANFILE: GenConanfile()})
        client.run("export-pkg . --name=hello --version=0.1 --user=lasote --channel=stable")
        self.assertIn("hello/0.1@lasote/stable package(): WARN: No files in this package!",
                      client.out)

    def test_develop(self):
        # https://github.com/conan-io/conan/issues/2513
        conanfile = """from conans import ConanFile
class helloPythonConan(ConanFile):
    def package(self):
        self.output.info("DEVELOP IS: %s!" % self.develop)
"""
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export-pkg . --name=hello --version=0.1 --user=lasote --channel=stable ")
        self.assertIn("hello/0.1@lasote/stable: DEVELOP IS: True!", client.out)

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_options(self):
        # https://github.com/conan-io/conan/issues/2242
        conanfile = """from conans import ConanFile
class helloPythonConan(ConanFile):
    name = "hello"
    options = { "optionOne": [True, False, 123] }
    default_options = "optionOne=True"
"""
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export-pkg . --name=hello --version=0.1 --user=lasote --channel=stable")
        client.run("search hello/0.1@lasote/stable")
        self.assertIn("optionOne: True", client.out)
        self.assertNotIn("optionOne: False", client.out)
        self.assertNotIn("optionOne: 123", client.out)
        client.run("export-pkg . --name=hello --version=0.1 --user=lasote --channel=stable -o optionOne=False")
        client.run("search hello/0.1@lasote/stable")
        self.assertIn("optionOne: True", client.out)
        self.assertIn("optionOne: False", client.out)
        self.assertNotIn("optionOne: 123", client.out)
        client.run("export-pkg . --name=hello --version=0.1 --user=lasote --channel=stable -o hello:optionOne=123")
        client.run("search hello/0.1@lasote/stable")
        self.assertIn("optionOne: True", client.out)
        self.assertIn("optionOne: False", client.out)
        self.assertIn("optionOne: 123", client.out)

    def test_profile_environment(self):
        # https://github.com/conan-io/conan/issues/4832
        conanfile = dedent("""
            import os
            from conans import ConanFile
            from conan.tools.env import VirtualBuildEnv
            class helloPythonConan(ConanFile):
                def package(self):
                    build_env = VirtualBuildEnv(self).vars()
                    with build_env.apply():
                        self.output.info("ENV-VALUE: %s!!!" % os.getenv("MYCUSTOMVAR"))
            """)
        profile = dedent("""
            [buildenv]
            MYCUSTOMVAR=MYCUSTOMVALUE
            """)
        client = TestClient()
        client.save({CONANFILE: conanfile,
                     "myprofile": profile})
        client.run("export-pkg . --name=hello --version=0.1 --user=lasote --channel=stable "
                   " -pr=myprofile")
        self.assertIn("hello/0.1@lasote/stable: ENV-VALUE: MYCUSTOMVALUE!!!", client.out)

    def _consume(self, client, install_args):
        consumer = """
from conans import ConanFile
class TestConan(ConanFile):
    requires = "hello/0.1@lasote/stable"
    settings = "os", "build_type"
"""
        client.save({CONANFILE: consumer}, clean_first=True)
        client.run("install %s" % install_args)
        self.assertIn("hello/0.1@lasote/stable: Already installed!", client.out)

    def test_build_folders(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "hello"
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
        client.run("export-pkg . --user=lasote --channel=stable -s os=Windows")
        package_id = re.search(r"Packaging to (\S+)", str(client.out)).group(1)
        prev = re.search(r"Created package revision (\S+)", str(client.out)).group(1)
        pref = PkgReference.loads(f"hello/0.1@lasote/stable#9583c5d0a62cd7afe4f83f821bf37be2:{package_id}#{prev}")
        package_folder = client.cache.pkg_layout(pref).package()
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
        client.run("export-pkg . --name=hello --version=0.1 --user=lasote --channel=stable "
                   "-s os=Windows")
        package_id = re.search(r"Packaging to (\S+)", str(client.out)).group(1)
        prev = re.search(r"Created package revision (\S+)", str(client.out)).group(1)
        pref = PkgReference.loads(f"hello/0.1@lasote/stable#cd0221af3af8be9e3d7e7b6ae56ce0b6:{package_id}#{prev}")

        package_folder = client.cache.pkg_layout(pref).package()
        header = os.path.join(package_folder, "include/header.h")
        self.assertTrue(os.path.exists(header))

        hello_path = os.path.join(package_folder, "lib", "hello.lib")
        self.assertTrue(os.path.exists(hello_path))

    def test_build_source_folders(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class TestConan(ConanFile):
    settings = "os"
    name = "hello"
    version = "0.1"

    def layout(self):
        self.folders.build = "build"
        self.folders.source = "src"

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
        client.run("export-pkg . --user=lasote --channel=stable -s os=Windows")
        rrev = re.search(r"Exported revision: (\S+)", str(client.out)).group(1)
        package_id = re.search(r"Packaging to (\S+)", str(client.out)).group(1)
        prev = re.search(r"Created package revision (\S+)", str(client.out)).group(1)
        pref = PkgReference.loads(f"hello/0.1@lasote/stable#{rrev}:{package_id}#{prev}")
        package_folder = client.cache.pkg_layout(pref).package()
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
    name = "hello"
    version = "0.1"
    settings = "os"

    def package(self):
        self.copy("*")
"""
        # Partial reference is ok
        client.save({CONANFILE: conanfile, "file.txt": "txt contents"})
        client.run("export-pkg . --user=conan --channel=stable ")
        self.assertIn("hello/0.1@conan/stable package(): Packaged 1 '.txt' file: file.txt",
                      client.out)

        # Specify different name or version is not working
        client.run("export-pkg . --name=lib", assert_error=True)
        self.assertIn("ERROR: Package recipe with name lib!=hello", client.out)

        client.run("export-pkg . --version=1.1", assert_error=True)
        self.assertIn("ERROR: Package recipe with version 1.1!=0.1", client.out)

        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    settings = "os"

    def package(self):
        self.copy("*")
"""
        # Partial reference is ok
        client.save({CONANFILE: conanfile, "file.txt": "txt contents"})
        client.run("export-pkg . --name=anyname --version=1.222 --user=conan --channel=stable")
        self.assertIn("anyname/1.222@conan/stable package(): Packaged 1 '.txt' file: file.txt",
                      client.out)

    def test_with_deps(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=hello --version=0.1 --user=lasote --channel=stable")
        conanfile = GenConanfile().with_name("hello1").with_version("0.1")\
                                  .with_import("from conans import tools")\
                                  .with_require("hello/0.1@lasote/stable")

        conanfile = str(conanfile) + """\n    def package_info(self):
        self.cpp_info.libs = tools.collect_libs(self)
    def layout(self):
        self.folders.build = "Release_x86"
    def package(self):
        self.copy("*")
        """
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.save({"Release_x86/lib/libmycoollib.a": ""})
        settings = ('-s os=Windows -s compiler=gcc -s compiler.version=4.9 '
                    '-s compiler.libcxx=libstdc++ -s build_type=Release -s arch=x86')
        client.run("export-pkg . --name=hello1 --version=0.1 --user=lasote --channel=stable %s"
                   % settings)

        # consumer
        consumer = """
from conans import ConanFile
class TestConan(ConanFile):
    requires = "hello1/0.1@lasote/stable"
    settings = "os", "build_type"
"""
        client.save({CONANFILE: consumer}, clean_first=True)
        client.run("install conanfile.py -g CMakeDeps")
        self.assertIn("hello/0.1@lasote/stable: Already installed!", client.out)
        self.assertIn("hello1/0.1@lasote/stable: Already installed!", client.out)

        cmakeinfo = client.load("hello1-release-data.cmake")
        self.assertIn("set(hello1_LIBS_RELEASE mycoollib)", cmakeinfo)

    @pytest.mark.xfail(reason="JSon output to be revisited, because based on ActionRecorder")
    def test_export_pkg_json(self):

        def _check_json_output_no_folder():
            json_path = os.path.join(self.client.current_folder, "output.json")
            self.assertTrue(os.path.exists(json_path))
            json_content = load(json_path)
            output = json.loads(json_content)
            self.assertEqual(True, output["error"])
            self.assertEqual([], output["installed"])
            self.assertEqual(2, len(output))

        def _check_json_output(with_error=False):
            json_path = os.path.join(self.client.current_folder, "output.json")
            self.assertTrue(os.path.exists(json_path))
            json_content = load(json_path)
            output = json.loads(json_content)
            self.assertEqual(output["error"], with_error)
            tmp = RecipeReference.loads(output["installed"][0]["recipe"]["id"])
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

        _check_json_output_no_folder()

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

    @pytest.mark.xfail(reason="JSon output to be revisited, because based on ActionRecorder")
    def test_json_with_dependencies(self):

        def _check_json_output(with_error=False):
            json_path = os.path.join(self.client.current_folder, "output.json")
            self.assertTrue(os.path.exists(json_path))
            json_content = load(json_path)
            output = json.loads(json_content)
            self.assertEqual(output["error"], with_error)
            tmp = RecipeReference.loads(output["installed"][0]["recipe"]["id"])
            self.assertIsNotNone(tmp.revision)
            self.assertEqual(str(tmp), "pkg2/1.0@danimtb/testing")
            self.assertFalse(output["installed"][0]["recipe"]["dependency"])
            self.assertTrue(output["installed"][0]["recipe"]["exported"])
            if with_error:
                self.assertEqual(output["installed"][0]["packages"], [])
            else:
                self.assertEqual(output["installed"][0]["packages"][0]["id"],
                                 "41e2f19ba15c770149de4cefcf9dd1d1f6ee19ce")
                self.assertTrue(output["installed"][0]["packages"][0]["exported"])
                tmp = RecipeReference.loads(output["installed"][1]["recipe"]["id"])
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
        self.client.run("export conanfile_dep.py --name=pkg1 --version=1.0 --user=danimtb --channel=testing")
        self.client.run("export-pkg conanfile.py --name=pkg2 --version=1.0 --user=danimtb --channel=testing --json output.json")
        _check_json_output()

        # Error on missing dependency
        self.client.run("remove pkg1/1.0@danimtb/testing --force")
        self.client.run("remove pkg2/1.0@danimtb/testing --force")
        self.client.run("export-pkg conanfile.py --name=pkg2 --version=1.0 --user=danimtb --channel=testing --json output.json",
                        assert_error=True)
        _check_json_output(with_error=True)

    def test_export_pkg_no_ref(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class TestConan(ConanFile):
    name = "hello"
    version = "0.1"

    def package(self):
        self.copy("*.h", src="src", dst="include")
"""
        client.save({CONANFILE: conanfile,
                     "src/header.h": "contents"})
        client.run("export-pkg . -s os=Windows")
        prev = re.search(r"Created package revision (\S+)", str(client.out)).group(1)
        pref = PkgReference.loads(f"hello/0.1#fa5edd1a46331a25cb2f4258cde84f9a:{NO_SETTINGS_PACKAGE_ID}#{prev}")
        package_folder = client.cache.pkg_layout(pref).package()
        header = os.path.join(package_folder, "include/header.h")
        self.assertTrue(os.path.exists(header))


def test_build_policy_never():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            build_policy = "never"

            def package(self):
                self.copy("*.h", src="src", dst="include")
        """)
    client.save({CONANFILE: conanfile,
                 "src/header.h": "contents"})
    client.run("export-pkg . --name=pkg --version=1.0")
    assert "pkg/1.0 package(): Packaged 1 '.h' file: header.h" in client.out

    client.run("install --reference=pkg/1.0@ --build")
    client.assert_listed_require({"pkg/1.0": "Cache"})
    assert "pkg/1.0: Calling build()" not in client.out


def test_build_policy_never_missing():
    # https://github.com/conan-io/conan/issues/9798
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_class_attribute('build_policy = "never"'),
                 "consumer.txt": "[requires]\npkg/1.0"})
    client.run("export . --name=pkg --version=1.0")

    client.run("install --reference=pkg/1.0@ --build", assert_error=True)
    assert "ERROR: Missing binary: pkg/1.0" in client.out

    client.run("install --reference=pkg/1.0@ --build=missing", assert_error=True)
    print(client.out)
    assert "ERROR: Missing binary: pkg/1.0" in client.out
