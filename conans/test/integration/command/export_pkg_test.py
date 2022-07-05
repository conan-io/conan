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
from conans.util.files import load


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
        conanfile = """from conan import ConanFile
class PkgB(ConanFile):
    settings = "arch"
    requires = "pkgc/0.1@user/testing"
"""
        client.save({CONANFILE: conanfile})
        client.run("create . --name=pkgb --version=0.1 --user=user --channel=testing")
        conanfile = """from conan import ConanFile
class PkgA(ConanFile):
    requires = "pkgb/0.1@user/testing"
    def build(self):
        self.output.info("BUILDING PKGA")
"""
        client.save({CONANFILE: conanfile})
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

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_options(self):
        # https://github.com/conan-io/conan/issues/2242
        conanfile = """from conan import ConanFile
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
        client.run("export-pkg . --name=hello --version=0.1 --user=lasote --channel=stable -o hello/*:optionOne=123")
        client.run("search hello/0.1@lasote/stable")
        self.assertIn("optionOne: True", client.out)
        self.assertIn("optionOne: False", client.out)
        self.assertIn("optionOne: 123", client.out)

    def test_profile_environment(self):
        # https://github.com/conan-io/conan/issues/4832
        conanfile = dedent("""
            import os
            from conan import ConanFile
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
from conan import ConanFile
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
import os
from conan import ConanFile
from conan.tools.files import save, copy
class TestConan(ConanFile):
    name = "hello"
    version = "0.1"
    settings = "os"

    def package(self):
        copy(self, "*.h", os.path.join(self.source_folder, "include"),
             os.path.join(self.package_folder, "inc"))
        copy(self, "*.lib", os.path.join(self.build_folder, "lib"),
             os.path.join(self.package_folder, "lib"))
"""
        client.save({CONANFILE: conanfile,
                     "include/header.h": "//Windows header",
                     "include/header.txt": "",
                     "libs/what": "",
                     "lib/hello.lib": "My Lib",
                     "lib/bye.txt": ""}, clean_first=True)
        client.run("export-pkg . --user=lasote --channel=stable -s os=Windows")
        rrev = client.exported_recipe_revision()
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

    def test_default_source_folder(self):
        client = TestClient()
        conanfile = """
import os
from conan import ConanFile
from conan.tools.files import copy
class TestConan(ConanFile):

    def package(self):
        copy(self, "*.h", os.path.join(self.source_folder, "src"),
             os.path.join(self.package_folder, "include"))
        copy(self, "*.lib", self.build_folder, os.path.join(self.package_folder, "lib"),
             keep_path=False)
"""
        client.save({CONANFILE: conanfile,
                     "src/header.h": "contents",
                     "build/lib/hello.lib": "My Lib"})
        client.run("export-pkg . --name=hello --version=0.1 --user=lasote --channel=stable "
                   "-s os=Windows")
        rrev = client.exported_recipe_revision()
        package_id = re.search(r"Packaging to (\S+)", str(client.out)).group(1)
        prev = re.search(r"Created package revision (\S+)", str(client.out)).group(1)
        pref = PkgReference.loads(f"hello/0.1@lasote/stable#{rrev}:{package_id}#{prev}")

        package_folder = client.cache.pkg_layout(pref).package()
        header = os.path.join(package_folder, "include/header.h")
        self.assertTrue(os.path.exists(header))

        hello_path = os.path.join(package_folder, "lib", "hello.lib")
        self.assertTrue(os.path.exists(hello_path))

    def test_build_source_folders(self):
        client = TestClient()
        conanfile = """
import os
from conan import ConanFile
from conan.tools.files import copy
class TestConan(ConanFile):
    settings = "os"
    name = "hello"
    version = "0.1"

    def layout(self):
        self.folders.build = "build"
        self.folders.source = "src"

    def package(self):
        copy(self, "*.h", os.path.join(self.source_folder, "include"),
             os.path.join(self.package_folder, "inc"))
        copy(self, "*.lib", os.path.join(self.build_folder, "lib"),
             os.path.join(self.package_folder, "lib"))
"""
        client.save({CONANFILE: conanfile,
                     "src/include/header.h": "//Windows header",
                     "src/include/header.txt": "",
                     "build/libs/what": "",
                     "build/lib/hello.lib": "My Lib",
                     "build/lib/bye.txt": ""})
        client.run("export-pkg . --user=lasote --channel=stable -s os=Windows")
        rrev = client.exported_recipe_revision()
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
from conan import ConanFile
from conan.tools.files import copy
class TestConan(ConanFile):
    name = "hello"
    version = "0.1"
    settings = "os"

    def package(self):
        copy(self, "*", self.source_folder, self.package_folder)
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
from conan import ConanFile
from conan.tools.files import copy
class TestConan(ConanFile):
    settings = "os"

    def package(self):
        copy(self, "*", self.source_folder, self.package_folder)
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
                                  .with_import("from conan.tools.files import copy, collect_libs") \
                                  .with_require("hello/0.1@lasote/stable")

        conanfile = str(conanfile) + """\n    def package_info(self):
        self.cpp_info.libs = collect_libs(self)
    def layout(self):
        self.folders.build = "Release_x86"
    def package(self):
        copy(self, "*", self.source_folder, self.package_folder)
        copy(self, "*", self.build_folder, self.package_folder)
        """
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.save({"Release_x86/lib/libmycoollib.a": ""})
        settings = ('-s os=Windows -s compiler=gcc -s compiler.version=4.9 '
                    '-s compiler.libcxx=libstdc++ -s build_type=Release -s arch=x86')
        client.run("export-pkg . --name=hello1 --version=0.1 --user=lasote --channel=stable %s"
                   % settings)

        # consumer
        consumer = """
from conan import ConanFile
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

        conanfile = """from conan import ConanFile
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

        conanfile = """from conan import ConanFile
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
        conanfile = """import os
from conan import ConanFile
from conan.tools.files import copy
class TestConan(ConanFile):
    name = "hello"
    version = "0.1"

    def package(self):
        copy(self, "*.h", os.path.join(self.source_folder, "src"),
             os.path.join(self.package_folder, "include"))
"""
        client.save({CONANFILE: conanfile,
                     "src/header.h": "contents"})
        client.run("export-pkg . -s os=Windows")
        rrev = client.exported_recipe_revision()
        prev = re.search(r"Created package revision (\S+)", str(client.out)).group(1)
        pref = PkgReference.loads(f"hello/0.1#{rrev}:{NO_SETTINGS_PACKAGE_ID}#{prev}")
        package_folder = client.cache.pkg_layout(pref).package()
        header = os.path.join(package_folder, "include/header.h")
        self.assertTrue(os.path.exists(header))


def test_build_policy_never():
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy
        class TestConan(ConanFile):
            build_policy = "never"

            def package(self):
                copy(self, "*.h", os.path.join(self.source_folder, "src"),
                     os.path.join(self.package_folder, "include"))
        """)
    client.save({CONANFILE: conanfile,
                 "src/header.h": "contents"})
    client.run("export-pkg . --name=pkg --version=1.0")
    assert "pkg/1.0 package(): Packaged 1 '.h' file: header.h" in client.out
    # check for https://github.com/conan-io/conan/issues/10736
    client.run("export-pkg . --name=pkg --version=1.0")
    assert "pkg/1.0 package(): Packaged 1 '.h' file: header.h" in client.out
    client.run("install --requires=pkg/1.0@ --build='*'")
    client.assert_listed_require({"pkg/1.0": "Cache"})
    assert "pkg/1.0: Calling build()" not in client.out


def test_build_policy_never_missing():
    # https://github.com/conan-io/conan/issues/9798
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_class_attribute('build_policy = "never"'),
                 "consumer.txt": "[requires]\npkg/1.0"})
    client.run("export . --name=pkg --version=1.0")
    client.run("install --requires=pkg/1.0@ --build='*'", assert_error=True)
    assert "ERROR: Missing binary: pkg/1.0" in client.out

    client.run("install --requires=pkg/1.0@ --build=missing", assert_error=True)
    assert "ERROR: Missing binary: pkg/1.0" in client.out


def test_export_pkg_json_formatter():
    """
    Tests the ``conan export-pkg . -f json`` result
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class MyTest(ConanFile):
            name = "pkg"
            version = "0.2"

            def package_info(self):
                self.cpp_info.libs = ["pkg"]
                self.cpp_info.includedirs = ["path/includes/pkg", "other/include/path/pkg"]
                self.cpp_info.libdirs = ["one/lib/path/pkg"]
                self.cpp_info.defines = ["pkg_onedefinition", "pkg_twodefinition"]
                self.cpp_info.cflags = ["pkg_a_c_flag"]
                self.cpp_info.cxxflags = ["pkg_a_cxx_flag"]
                self.cpp_info.sharedlinkflags = ["pkg_shared_link_flag"]
                self.cpp_info.exelinkflags = ["pkg_exe_link_flag"]
                self.cpp_info.sysroot = "/path/to/folder/pkg"
                self.cpp_info.frameworks = ["pkg_oneframework", "pkg_twoframework"]
                self.cpp_info.system_libs = ["pkg_onesystemlib", "pkg_twosystemlib"]
                self.cpp_info.frameworkdirs = ["one/framework/path/pkg"]
                self.cpp_info.set_property("pkg_config_name", "pkg_other_name")
                self.cpp_info.set_property("pkg_config_aliases", ["pkg_alias1", "pkg_alias2"])
                self.cpp_info.components["cmp1"].libs = ["libcmp1"]
                self.cpp_info.components["cmp1"].set_property("pkg_config_name", "compo1")
                self.cpp_info.components["cmp1"].set_property("pkg_config_aliases", ["compo1_alias"])
                self.cpp_info.components["cmp1"].sysroot = "/another/sysroot"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    client.save({"conanfile.py": GenConanfile().with_name("hello").with_version("0.1")
                .with_require("pkg/0.2")}, clean_first=True)
    client.run("export-pkg . -f json")
    info = json.loads(client.stdout)
    nodes = info["graph"]["nodes"]
    hello_pkg_ref = 'hello/0.1#18d5440ae45afc4c36139a160ac071c7'
    pkg_pkg_ref = 'pkg/0.2#926714b5fb0a994f47ec37e071eba1da'
    hello_cpp_info = pkg_cpp_info = None
    for n in nodes:
        ref = n["ref"]
        if ref == hello_pkg_ref:
            assert n['binary'] == "Missing"
            hello_cpp_info = n['cpp_info']
        elif ref == pkg_pkg_ref:
            assert n['binary'] == "Cache"
            pkg_cpp_info = n['cpp_info']
    assert hello_cpp_info and pkg_cpp_info
    # hello/0.1 cpp_info
    assert hello_cpp_info['root']["libs"] is None
    assert len(hello_cpp_info['root']["bindirs"]) == 1
    assert len(hello_cpp_info['root']["libdirs"]) == 1
    assert hello_cpp_info['root']["sysroot"] is None
    assert hello_cpp_info['root']["properties"] is None
    # pkg/0.2 cpp_info
    # root info
    assert pkg_cpp_info['root']["libs"] is None
    assert len(pkg_cpp_info['root']["bindirs"]) == 1
    assert len(pkg_cpp_info['root']["libdirs"]) == 1
    assert pkg_cpp_info['root']["sysroot"] is None
    assert pkg_cpp_info['root']["system_libs"] is None
    assert pkg_cpp_info['root']['cflags'] is None
    assert pkg_cpp_info['root']['cxxflags'] is None
    assert pkg_cpp_info['root']['defines'] is None
    assert pkg_cpp_info['root']["properties"] is None
    # component info
    assert pkg_cpp_info.get('cmp1') is None
