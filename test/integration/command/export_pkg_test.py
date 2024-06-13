import json
import os
import re

import textwrap
import unittest
from textwrap import dedent

from conan.internal.paths import CONANFILE
from conan.test.utils.tools import TestClient, GenConanfile
from conans.util.files import load


class ExportPkgTest(unittest.TestCase):

    def test_dont_touch_server(self):
        # https://github.com/conan-io/conan/issues/3432
        client = TestClient(servers={"default": None},
                            requester_class=None, inputs=["admin", "password"])

        client.save({"conanfile.py": GenConanfile().with_name("pkg").with_version("0.1")})
        client.run("install .")
        client.run("export-pkg . --user=lasote --channel=stable ")

    def test_transitive_without_settings(self):
        # https://github.com/conan-io/conan/issues/3367
        client = TestClient()
        client.save({"pkgc/conanfile.py": GenConanfile("pkgc", "0.1"),
                     "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkgc/0.1"),
                     "pkga/conanfile.py": GenConanfile("pkga", "0.1").with_requires("pkgb/0.1")})
        client.run("create pkgc")
        client.run("create pkgb")

        client.run("build pkga -bf=build")
        client.run("export-pkg pkga ")
        package_id = re.search(r"Packaging to (\S+)", str(client.out)).group(1)
        self.assertIn(f"conanfile.py (pkga/0.1): Package '{package_id}' created", client.out)

        # we can export-pkg without the dependencies binaries if we need to optimize
        client.run("remove pkgc*:* -c")
        client.run("remove pkgb*:* -c")
        client.run("export-pkg pkga --skip-binaries")
        package_id = re.search(r"Packaging to (\S+)", str(client.out)).group(1)
        self.assertIn(f"conanfile.py (pkga/0.1): Package '{package_id}' created", client.out)

    def test_package_folder_errors(self):
        # https://github.com/conan-io/conan/issues/2350
        client = TestClient()
        client.save({CONANFILE: GenConanfile()})
        client.run("export-pkg . --name=hello --version=0.1 --user=lasote --channel=stable")
        self.assertIn("conanfile.py (hello/0.1@lasote/stable): package(): "
                      "WARN: No files in this package!", client.out)

    def test_options(self):
        # https://github.com/conan-io/conan/issues/2242
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Hello(ConanFile):
                name = "hello"
                version = "0.1"
                options = { "optionOne": [True, False, 123] }
                default_options =  {"optionOne": True}
            """)
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export-pkg .")
        client.run("list hello/0.1:*")
        self.assertIn("optionOne: True", client.out)
        self.assertNotIn("optionOne: False", client.out)
        self.assertNotIn("optionOne: 123", client.out)
        client.run("export-pkg . -o optionOne=False")
        client.run("list hello/0.1:*")
        self.assertIn("optionOne: True", client.out)
        self.assertIn("optionOne: False", client.out)
        self.assertNotIn("optionOne: 123", client.out)
        client.run("export-pkg . -o hello/*:optionOne=123")
        client.run("list hello/0.1:*")
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
        self.assertIn("conanfile.py (hello/0.1@lasote/stable): ENV-VALUE: MYCUSTOMVALUE!!!",
                      client.out)

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
        client.run("export-pkg . --user=lasote --channel=stable -s os=Windows -vvv")
        assert "copy(pattern=*.h) copied 1 files" in client.out
        assert "copy(pattern=*.lib) copied 1 files" in client.out
        package_folder = client.created_layout().package()
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

        package_folder = client.created_layout().package()
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

        package_folder = client.created_layout().package()
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
        client.run("export-pkg . --user=conan --channel=stable")
        self.assertIn("conanfile.py (hello/0.1@conan/stable): package(): "
                      "Packaged 1 '.txt' file: file.txt", client.out)

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
        self.assertIn("conanfile.py (anyname/1.222@conan/stable): package(): "
                      "Packaged 1 '.txt' file: file.txt", client.out)

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

    def test_export_pkg_json(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("pkg", "0.1")})

        # Wrong folders
        client.run("export-pkg . --format=json", redirect_stdout="exported.json")
        graph = json.loads(client.load("exported.json"))
        node = graph["graph"]["nodes"]["0"]
        assert "pkg/0.1" in node["ref"]
        # https://github.com/conan-io/conan/issues/15041
        assert "da39a3ee5e6b4b0d3255bfef95601890afd80709" == node["package_id"]
        assert "485dad6cb11e2fa99d9afbe44a57a164" == node["rrev"]
        assert "0ba8627bd47edc3a501e8f0eb9a79e5e" == node["prev"]
        assert "Build" == node["binary"]
        assert node["rrev_timestamp"] is not None
        assert node["prev_timestamp"] is not None

        # Make sure the exported json file can be used for ``conan lsit --graph`` input to upload
        client.run("list --graph=exported.json -gb=build --format=json")
        pkglist = json.loads(client.stdout)
        revs = pkglist["Local Cache"]["pkg/0.1"]["revisions"]["485dad6cb11e2fa99d9afbe44a57a164"]
        assert "da39a3ee5e6b4b0d3255bfef95601890afd80709" in revs["packages"]

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
        package_folder = client.created_layout().package()
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
    assert "conanfile.py (pkg/1.0): package(): Packaged 1 '.h' file: header.h" in client.out
    # check for https://github.com/conan-io/conan/issues/10736
    client.run("export-pkg . --name=pkg --version=1.0")
    assert "conanfile.py (pkg/1.0): package(): Packaged 1 '.h' file: header.h" in client.out
    client.run("install --requires=pkg/1.0@ --build='*'")
    client.assert_listed_require({"pkg/1.0": "Cache"})
    assert "conanfile.py (pkg/1.0): Calling build()" not in client.out


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
    for n in nodes.values():
        ref = n["ref"]
        if ref == hello_pkg_ref:
            assert n['binary'] == "Build"
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

    assert pkg_cpp_info['root']["libs"] == ['pkg']
    assert len(pkg_cpp_info['root']["bindirs"]) == 1
    assert len(pkg_cpp_info['root']["libdirs"]) == 1
    assert pkg_cpp_info['root']["sysroot"] == '/path/to/folder/pkg'
    assert pkg_cpp_info['root']["system_libs"] == ['pkg_onesystemlib', 'pkg_twosystemlib']
    assert pkg_cpp_info['root']['cflags'] == ['pkg_a_c_flag']
    assert pkg_cpp_info['root']['cxxflags'] == ['pkg_a_cxx_flag']
    assert pkg_cpp_info['root']['defines'] == ['pkg_onedefinition', 'pkg_twodefinition']
    assert pkg_cpp_info['root']["properties"] == {'pkg_config_name': 'pkg_other_name',
                                                  'pkg_config_aliases': ['pkg_alias1', 'pkg_alias2']}
    # component info
    assert pkg_cpp_info["cmp1"]["libs"] == ["libcmp1"]


def test_export_pkg_dont_update_src():
    """
    There was a bug in 1.X and sources were not updated correctly in export-pkg
    close https://github.com/conan-io/conan/issues/6041
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import load
        class Hello(ConanFile):
            name = "hello"
            version = "0.1"
            exports_sources = "*.cpp"
            def build(self):
                content = load(self, "src/hello.cpp")
                self.output.info("CONTENT: {}".format(content))
        """)

    c.save({"conanfile.py": conanfile,
            "src/hello.cpp": "old code!"})
    c.run("install .")
    c.run("build .")
    c.run("export-pkg .")
    c.run("install --requires=hello/0.1@ --build=hello*")
    assert "hello/0.1: CONTENT: old code!" in c.out
    # Now locally change the source code
    c.save({"src/hello.cpp": "updated code!"})
    c.run("install .")
    c.run("build .")
    c.run("export-pkg .")
    c.run("install --requires=hello/0.1@ --build=hello*")
    assert "hello/0.1: CONTENT: updated code!" in c.out


def test_negate_tool_requires():
    c = TestClient()
    profile = textwrap.dedent("""
        [tool_requires]
        !mypkg/*:cmake/3.24
        """)
    c.save({"myprofile": profile,
            "conanfile.py": GenConanfile("mypkg", "0.1")})
    c.run("export-pkg . -pr=myprofile")
    assert "conanfile.py (mypkg/0.1): Created package" in c.out


def test_export_pkg_tool_requires():
    """ when a package has "tool_requires" that it needs at the package() method, like
    typical cmake.install() or autotools.install() (tool_require msys2), then it is necessary:
    - to install the dependencies
    - to inject the tool-requirements
    - to propagate the environment and the conf
    """
    c = TestClient(default_server_user=True)
    tool = textwrap.dedent("""
        from conan import ConanFile
        class Tool(ConanFile):
            name = "tool"
            version = "0.1"
            def package_info(self):
                self.buildenv_info.define("MYVAR", "MYVALUE")
                self.conf_info.define("user.team:conf", "CONF_VALUE")
            """)
    consumer = textwrap.dedent("""
        import platform
        from conan import ConanFile

        class Consumer(ConanFile):
            name = "consumer"
            version = "0.1"
            tool_requires = "tool/0.1"
            def package(self):
                self.output.info(f"MYCONF {self.conf.get('user.team:conf')}")
                cmd = "set MYVAR" if platform.system() == "Windows" else "echo MYVAR=$MYVAR"
                self.run(cmd)
            """)
    c.save({"tool/conanfile.py": tool,
            "consumer/conanfile.py": consumer})

    c.run("create tool")
    c.run("export-pkg consumer")
    assert "conanfile.py (consumer/0.1): MYCONF CONF_VALUE" in c.out
    assert "MYVAR=MYVALUE" in c.out
    c.run("upload tool* -r=default -c")
    c.run("remove tool* -c")
    c.run("export-pkg consumer")
    assert "conanfile.py (consumer/0.1): MYCONF CONF_VALUE" in c.out
    assert "MYVAR=MYVALUE" in c.out


def test_export_pkg_output_folder():
    """ If the local build is using a different output-folder, it should work and export it
    """
    c = TestClient()
    consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save, copy

        class Consumer(ConanFile):
            name = "consumer"
            version = "0.1"

            def build(self):
                save(self, "myfile.txt", "")
            def package(self):
                copy(self, "*", src=self.build_folder, dst=self.package_folder)
            """)
    c.save({"conanfile.py": consumer})

    c.run("build . -of=mytmp")
    c.run("export-pkg . -of=mytmp")
    assert "Packaged 1 '.txt' file: myfile.txt" in c.out
    assert os.path.exists(os.path.join(c.current_folder, "mytmp", "myfile.txt"))


def test_export_pkg_test_package():
    """ If there is a test_package, run it
    """
    c = TestClient()
    test_conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Test(ConanFile):
            def requirements(self):
                self.requires(self.tested_reference_str)
            def test(self):
                self.output.info("RUN TEST PACKAGE!!!!")
            """)
    c.save({"conanfile.py": GenConanfile("pkg", "1.0"),
            "test_package/conanfile.py": test_conanfile})

    c.run("export-pkg . ")
    assert "test_package" in c.out
    assert "RUN TEST PACKAGE!!!!" in c.out

    c.run('export-pkg . -tf=""')
    assert "test_package" not in c.out
    assert "RUN TEST" not in c.out


def test_export_pkg_test_package_build_require():
    """ Test --build-require
    """
    c = TestClient()
    test_conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Test(ConanFile):
            def build_requirements(self):
                self.tool_requires(self.tested_reference_str)
            def test(self):
                self.output.info(f"RUN TEST PACKAGE!!!!")
            """)
    c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_setting("os"),
            "test_package/conanfile.py": test_conanfile})

    c.run("export-pkg . -s:b os=Windows -s:h os=Linux --build-require --lockfile-out=conan.lock")
    assert "test_package" in c.out
    assert "RUN TEST PACKAGE!!!!" in c.out
    lock = json.loads(c.load("conan.lock"))
    assert "pkg/1.0" in lock["build_requires"][0]


def test_export_pkg_remote_python_requires():
    """ Test that remote python-requires can be resolved
    """
    c = TestClient(default_server_user=True)
    c.save({"tool/conanfile.py": GenConanfile("tool", "1.0"),
            "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_python_requires("tool/1.0")})

    c.run("create tool")
    c.run("upload tool* -r=default -c")
    c.run("remove * -c")
    c.run("export-pkg pkg")
    assert "conanfile.py (pkg/1.0): Exported package binary" in c.out


def test_remote_none():
    # https://github.com/conan-io/conan/pull/14705
    c = TestClient(default_server_user=True)
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "pkg/conanfile.py": GenConanfile("pkg", "0.1"),
            "pkg/test_package/conanfile.py": GenConanfile().with_test("pass").with_requires("dep/0.1")})
    c.run("create dep")
    c.run("upload dep* -r=default -c")
    c.run("build pkg")
    c.run("remove dep*:* -c")
    c.run("export-pkg pkg")    # This used to crash
    # No longer crash
    assert "pkg/0.1 (test package): Running test()" in c.out


def test_remote_none_tool_requires():
    # https://github.com/conan-io/conan/pull/14705
    c = TestClient(default_server_user=True)
    c.save({"tool/conanfile.py": GenConanfile("tool", "0.1").with_settings("compiler"),
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_tool_requires("tool/0.1"),
            "pkg/test_package/conanfile.py": GenConanfile().with_test("pass")})
    settings = "-s:b compiler=gcc -s:b compiler.version=9 -s:b compiler.libcxx=libstdc++11"
    c.run(f"create tool {settings} -s:b compiler.cppstd=20 --build-require")
    c.run(f"build pkg {settings} -s:b compiler.cppstd=17")
    c.run(f"export-pkg pkg {settings} -s:b compiler.cppstd=17")  # This used to crash
    # No longer crash
    assert "pkg/0.1 (test package): Running test()" in c.out


def test_export_pkg_set_version_python_requires():
    # https://github.com/conan-io/conan/issues/16223
    c = TestClient(light=True)
    py_require = textwrap.dedent("""
        from conan import ConanFile

        class TestBuild:
            def set_version(self):
                assert self.version

        class TestModule(ConanFile):
            name = "pyreq"
            version = "0.1"
            package_type = "python-require"
    """)
    pkg = textwrap.dedent("""
        from conan import ConanFile

        class TestPkgConan(ConanFile):
            name="testpkg"
            python_requires = "pyreq/0.1"
            python_requires_extend = "pyreq.TestBuild"
        """)
    c.save({"pyreq/conanfile.py": py_require,
            "pkg/conanfile.py": pkg})

    c.run("create pyreq")
    c.run("export-pkg pkg --version=1.0+0")
    assert "conanfile.py (testpkg/1.0+0): Exported package binary" in c.out
