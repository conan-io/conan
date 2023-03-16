import json
import os
import re
import textwrap
import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID, GenConanfile
from conans.util.files import load, save


class CreateTest(unittest.TestCase):

    def test_dependencies_order_matches_requires(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=pkga --version=0.1 --user=user --channel=testing")
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=pkgb --version=0.1 --user=user --channel=testing")
        conanfile = textwrap.dedent("""
            [requires]
            pkgb/0.1@user/testing
            pkga/0.1@user/testing
            """)
        client.save({"conanfile.txt": conanfile}, clean_first=True)
        client.run("install . -g MSBuildDeps -s build_type=Release -s arch=x86")
        conandeps = client.load("conandeps.props")
        assert conandeps.find("pkgb") < conandeps.find("pkga")

    def test_create(self):
        client = TestClient()
        client.save({"conanfile.py": """from conan import ConanFile
class MyPkg(ConanFile):
    def source(self):
        assert(self.version=="0.1")
        assert(self.name=="pkg")
    def configure(self):
        assert(self.version=="0.1")
        assert(self.name=="pkg")
    def requirements(self):
        assert(self.version=="0.1")
        assert(self.name=="pkg")
    def build(self):
        assert(self.version=="0.1")
        assert(self.name=="pkg")
    def package(self):
        assert(self.version=="0.1")
        assert(self.name=="pkg")
    def package_info(self):
        assert(self.version=="0.1")
        assert(self.name=="pkg")
    def system_requirements(self):
        assert(self.version=="0.1")
        assert(self.name=="pkg")
        self.output.info("Running system requirements!!")
"""})
        client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")
        self.assertIn("Profile host:\n[settings]", client.out)
        self.assertIn("pkg/0.1@lasote/testing: Generating the package", client.out)
        self.assertIn("Running system requirements!!", client.out)
        client.run('list -c *')
        self.assertIn("pkg/0.1@lasote/testing", client.out)

        # Create with only user will raise an error because of no name/version
        client.run("create conanfile.py --user=lasote --channel=testing", assert_error=True)
        self.assertIn("ERROR: conanfile didn't specify name", client.out)
        # Create with user but no channel should be valid
        client.run("create . --name=pkg --version=0.1 --user=lasote")
        assert "pkg/0.1@lasote:" in client.out


    def test_error_create_name_version(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("hello").with_version("1.2")})
        client.run("create . --name=hello --version=1.2 --user=lasote --channel=stable")
        client.run("create . --name=pkg", assert_error=True)
        self.assertIn("ERROR: Package recipe with name pkg!=hello", client.out)
        client.run("create . --version=1.1", assert_error=True)
        self.assertIn("ERROR: Package recipe with version 1.1!=1.2", client.out)

    def test_create_user_channel(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("pkg").with_version("0.1")})
        client.run("create . --user=lasote --channel=channel")
        self.assertIn("pkg/0.1@lasote/channel: Generating the package", client.out)
        client.run("list * -c")
        self.assertIn("pkg/0.1@lasote/channel", client.out)
        
        # test default without user and channel
        client.run("create . ")
        self.assertIn("pkg/0.1: Generating the package", client.out)

    def test_create_in_subfolder(self):
        client = TestClient()
        client.save({"subfolder/conanfile.py": GenConanfile().with_name("pkg").with_version("0.1")})
        client.run("create subfolder --user=lasote --channel=channel")
        self.assertIn("pkg/0.1@lasote/channel: Generating the package", client.out)
        client.run("list * -c")
        self.assertIn("pkg/0.1@lasote/channel", client.out)

    def test_create_in_subfolder_with_different_name(self):
        # Now with a different name
        client = TestClient()
        client.save({"subfolder/Custom.py": GenConanfile().with_name("pkg").with_version("0.1")})
        client.run("create subfolder/Custom.py --user=lasote --channel=channel")
        self.assertIn("pkg/0.1@lasote/channel: Generating the package", client.out)
        client.run("list * -c")
        self.assertIn("pkg/0.1@lasote/channel", client.out)

    def test_create_test_package(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("pkg").with_version("0.1"),
                     "test_package/conanfile.py":
                         GenConanfile().with_test('self.output.info("TESTING!!!")')})
        client.run("create . --user=lasote --channel=testing")
        self.assertIn("pkg/0.1@lasote/testing: Generating the package", client.out)
        self.assertIn("pkg/0.1@lasote/testing (test package): TESTING!!!", client.out)

    def test_create_skip_test_package(self):
        # Skip the test package stage if explicitly disabled with --test-folder=None
        # https://github.com/conan-io/conan/issues/2355
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("pkg").with_version("0.1"),
                     "test_package/conanfile.py":
                         GenConanfile().with_test('self.output.info("TESTING!!!")')})
        client.run("create . --user=lasote --channel=testing --test-folder=\"\"")
        self.assertIn("pkg/0.1@lasote/testing: Generating the package", client.out)
        self.assertNotIn("TESTING!!!", client.out)

    def test_create_package_requires(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=dep --version=0.1 --user=user --channel=channel")
        client.run("create . --name=other --version=1.0 --user=user --channel=channel")

        conanfile = GenConanfile().with_require("dep/0.1@user/channel")
        test_conanfile = """from conan import ConanFile
class MyPkg(ConanFile):
    requires = "other/1.0@user/channel"
    def requirements(self):
        self.requires(self.tested_reference_str)
    def build(self):
        for r in self.requires.values():
            self.output.info("build() Requires: %s" % str(r.ref))
        import os
        for dep in self.dependencies.host.values():
            self.output.info("build() cpp_info dep: %s" % dep)

    def test(self):
        pass
        """

        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile})

        client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")

        self.assertIn("pkg/0.1@lasote/testing (test package): build() "
                      "Requires: other/1.0@user/channel", client.out)
        self.assertIn("pkg/0.1@lasote/testing (test package): build() "
                      "Requires: pkg/0.1@lasote/testing", client.out)
        self.assertIn("pkg/0.1@lasote/testing (test package): build() cpp_info dep: other",
                      client.out)
        self.assertIn("pkg/0.1@lasote/testing (test package): build() cpp_info dep: dep",
                      client.out)
        self.assertIn("pkg/0.1@lasote/testing (test package): build() cpp_info dep: pkg",
                      client.out)

    @pytest.mark.xfail(reason="Legacy conan.conf configuration deprecated")
    def test_build_folder_handling(self):
        # FIXME: The "test_package" layout has changed, we need to discuss this redirection of
        #  the TEMP_TEST_FOLDER
        conanfile = GenConanfile().with_name("hello").with_version("0.1")
        test_conanfile = GenConanfile().with_test("pass")
        client = TestClient()
        default_build_dir = os.path.join(client.current_folder, "test_package", "build")

        # Test the default behavior.
        client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_conanfile},
                    clean_first=True)
        client.run("create . --user=lasote --channel=stable")
        self.assertTrue(os.path.exists(default_build_dir))

        # Test if the specified build folder is respected.
        client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_conanfile},
                    clean_first=True)
        client.run("create -tbf=build_folder . lasote/stable")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "build_folder")))
        self.assertFalse(os.path.exists(default_build_dir))

        # Test if using a temporary test folder can be enabled via the environment variable.
        client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_conanfile},
                    clean_first=True)
        with tools.environment_update({"CONAN_TEMP_TEST_FOLDER": "True"}):
            client.run("create . --user=lasote --channel=stable")
        self.assertFalse(os.path.exists(default_build_dir))

        # # Test if using a temporary test folder can be enabled via the config file.
        client.run("create . --user=lasote --channel=stable")
        self.assertFalse(os.path.exists(default_build_dir))

        # Test if the specified build folder is respected also when the use of
        # temporary test folders is enabled in the config file.
        client.run("create -tbf=test_package/build_folder . lasote/stable")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "test_package",
                                                    "build_folder")))
        self.assertFalse(os.path.exists(default_build_dir))

    def test_package_folder_build_error(self):
        """
        Check package folder is not created if the build step fails
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class MyPkg(ConanFile):

                def build(self):
                    raise Exception("Build error")
            """)
        client.save({"conanfile.py": conanfile})

        ref = RecipeReference("pkg", "0.1", "danimtb", "testing")
        client.run("create . --name=pkg --version=0.1 --user=danimtb --channel=testing",
                   assert_error=True)

        self.assertIn("Build error", client.out)
        pref = client.get_latest_package_reference(ref, NO_SETTINGS_PACKAGE_ID)
        assert pref is None

    def test_create_with_name_and_version(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run('create . --name=lib --version=1.0')
        self.assertIn("lib/1.0: Created package revision", client.out)

    def test_create_with_only_user_channel(self):
        """This should be the recommended way and only from Conan 2.0"""
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("lib").with_version("1.0")})
        client.run('create . --user=user --channel=channel')
        self.assertIn("lib/1.0@user/channel: Created package revision", client.out)

        client.run('create . --user=user --channel=channel')
        self.assertIn("lib/1.0@user/channel: Created package revision", client.out)

    def test_requires_without_user_channel(self):
        client = TestClient()
        conanfile = textwrap.dedent('''
            from conan import ConanFile

            class HelloConan(ConanFile):
                name = "hellobar"
                version = "0.1"

                def package_info(self):
                    self.output.warning("Hello, I'm hellobar")
            ''')

        client.save({"conanfile.py": conanfile})
        client.run("create .")

        client.save({"conanfile.py": GenConanfile().with_require("hellobar/0.1")})
        client.run("create . --name=consumer --version=1.0")
        self.assertIn("hellobar/0.1: WARN: Hello, I'm hellobar", client.out)
        self.assertIn("consumer/1.0: Created package revision", client.out)

    def test_conaninfo_contents_without_user_channel(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("hello").with_version("0.1")})
        client.run("create .")
        client.save({"conanfile.py": GenConanfile().with_name("bye").with_version("0.1")
                    .with_require("hello/0.1")})
        client.run("create .")

        ref = RecipeReference.loads("bye/0.1")

        refs = client.cache.get_latest_recipe_reference(ref)
        pkgs = client.cache.get_package_references(refs)
        prev = client.cache.get_latest_package_reference(pkgs[0])
        package_folder = client.cache.pkg_layout(prev).package()

        conaninfo = load(os.path.join(package_folder, "conaninfo.txt"))
        # The user and channel nor None nor "_/" appears in the conaninfo
        self.assertNotIn("None", conaninfo)
        self.assertNotIn("_/", conaninfo)
        self.assertNotIn("/_", conaninfo)
        self.assertIn("[requires]\nhello/0.1\n", conaninfo)

    def test_components_json_output(self):
        self.client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class MyTest(ConanFile):
                name = "pkg"
                version = "0.1"
                settings = "build_type"

                def package_info(self):
                    self.cpp_info.components["pkg1"].libs = ["libpkg1"]
                    self.cpp_info.components["pkg2"].libs = ["libpkg2"]
                    self.cpp_info.components["pkg2"].requires = ["pkg1"]
            """)
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . --format=json")
        data = json.loads(self.client.stdout)
        cpp_info_data = data["graph"]["nodes"][1]["cpp_info"]
        self.assertIn("libpkg1", cpp_info_data["pkg1"]["libs"])
        self.assertListEqual([], cpp_info_data["pkg1"]["requires"])
        self.assertIn("libpkg2", cpp_info_data["pkg2"]["libs"])
        self.assertListEqual(["pkg1"], cpp_info_data["pkg2"]["requires"])


def test_lockfile_input_not_specified():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_name("foo").with_version("1.0")})
    client.run("lock create . --lockfile-out locks/conan.lock")
    client.run("create . --lockfile-out locks/conan.lock")
    assert "Generated lockfile:" in client.out


def test_create_build_missing():
    """ test the --build=missing:pattern syntax
    """
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile("dep", "1.0").with_settings("os"),
            "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_settings("os")
           .with_requires("dep/1.0")})
    c.run("create dep -s os=Windows")

    # Wrong pattern will not build it
    c.run("create pkg -s os=Windows --build=missing:kk", assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkg/1.0'" in c.out

    # Pattern missing * will not build it
    c.run("create pkg -s os=Windows --build=missing:pkg", assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkg/1.0'" in c.out

    # Correct pattern pkg* will build it
    c.run("create pkg -s os=Windows --build=missing:pkg*")
    c.assert_listed_binary({"pkg/1.0": ("90887fdbe22295dfbe41afe0a45f960c6a72b650", "Build")})

    # Now anything that is not an explicit --build=pkg* will avoid rebuilding
    c.run("create pkg -s os=Windows --build=missing:kk")
    c.assert_listed_binary({"pkg/1.0": ("90887fdbe22295dfbe41afe0a45f960c6a72b650", "Cache")})
    assert "Calling build()" not in c.out

    # but dependency without binary will fail, even if right pkg* pattern
    c.run("create pkg -s os=Linux --build=missing:pkg*", assert_error=True)
    c.assert_listed_binary({"pkg/1.0": ("4c0c198b627f9af3e038af4da5e6b3ae205c2435", "Build")})
    c.assert_listed_binary({"dep/1.0": ("9a4eb3c8701508aa9458b1a73d0633783ecc2270", "Missing")})
    assert "ERROR: Missing prebuilt package for 'dep/1.0'" in c.out


def test_create_format_json():
    """
    Tests the ``conan create . -f json`` result

    The result should be something like:

    {
        'graph': {
            'nodes': [
                {'ref': '',  # consumer
                 'recipe': 'Virtual',
                 ....
                },
                {'ref': 'hello/0.1#18d5440ae45afc4c36139a160ac071c7',
                 'requires': {'2': 'pkg/0.2#db78b8d06a78af5c3ac56706f133098d'},
                 ....
                },
                {'ref': 'pkg/0.2#44a1a27ac2ea1fbcf434a05c4d57388d',
                 ....
                }
            ],
            'root': {'0': 'None'}
        }
    }
    """
    client = TestClient()
    profile_build = textwrap.dedent("""\
    [settings]
    arch=x86_64
    build_type=Release
    compiler=gcc
    compiler.libcxx=libstdc++
    compiler.version=12
    os=Linux
    [conf]
    user.first:value="my value"
    user.second:value=["my value"]
    user.second:value+=["other value"]
    [buildenv]
    VAR1=myvalue1
    """)
    profile_host = textwrap.dedent("""\
    [settings]
    arch=x86
    build_type=Debug
    compiler=gcc
    compiler.libcxx=libstdc++
    compiler.version=12
    os=Linux
    """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class MyTest(ConanFile):
            name = "pkg"
            version = "0.2"
            settings = "build_type", "compiler"
            author = "John Doe"
            license = "MIT"
            url = "https://foo.bar.baz"
            homepage = "https://foo.bar.site"
            topics = "foo", "bar", "qux"
            provides = "libjpeg", "libjpg"
            deprecated = "other-pkg"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}
        """)
    client.save({"conanfile.py": conanfile,
                 "host": profile_host, "build": profile_build})
    client.run("create . -pr:h host -pr:b build")
    client.save({"conanfile.py": GenConanfile().with_name("hello").with_version("0.1")
                .with_require("pkg/0.2"),
                 "host": profile_host, "build": profile_build}, clean_first=True)
    client.run("create . -f json -pr:h host -pr:b build")
    info = json.loads(client.stdout)
    nodes = info["graph"]['nodes']
    consumer_ref = 'conanfile'
    hello_pkg_ref = 'hello/0.1#18d5440ae45afc4c36139a160ac071c7'
    pkg_pkg_ref = 'pkg/0.2#db78b8d06a78af5c3ac56706f133098d'
    consumer_info = hello_pkg_info = pkg_pkg_info = None

    for n in nodes:
        ref = n["ref"]
        if ref == consumer_ref:
            consumer_info = n
        elif ref == hello_pkg_ref:
            hello_pkg_info = n
        elif ref == pkg_pkg_ref:
            pkg_pkg_info = n
        else:
            raise Exception("Ref not found. Review the revisions hash.")

    # Consumer information
    assert consumer_info["recipe"] == "Cli"
    assert consumer_info["package_id"] is None
    assert consumer_info["prev"] is None
    assert consumer_info["options"] == {}
    assert consumer_info["settings"] == {'arch': 'x86', 'build_type': 'Debug', 'compiler': 'gcc',
                                         'compiler.libcxx': 'libstdc++', 'compiler.version': '12',
                                         'os': 'Linux'}
    assert consumer_info["requires"] == {'1': hello_pkg_ref}
    # hello/0.1 pkg information
    assert hello_pkg_info["package_id"] == "8eba237c0fb239fcb7daa47979ab99258eaaa7d1"
    assert hello_pkg_info["prev"] == "d95380a07c35273509dfc36b26f6cec1"
    assert hello_pkg_info["settings"] == {}
    assert hello_pkg_info["options"] == {}
    assert hello_pkg_info["requires"] == {'2': pkg_pkg_ref}
    # pkg/0.2 pkg information
    assert pkg_pkg_info["package_id"] == "fb1439470288b15b2da269ed97b1a5f2f5d1f766"
    assert pkg_pkg_info["prev"] == "6949b0f89941d2a5994f9e6e4a89a331"
    assert pkg_pkg_info["author"] == 'John Doe'
    assert pkg_pkg_info["settings"] == {'build_type': 'Debug', 'compiler': 'gcc',
                                        'compiler.libcxx': 'libstdc++', 'compiler.version': '12'}
    assert pkg_pkg_info["options"] == {'fPIC': 'True', 'shared': 'False'}
    assert pkg_pkg_info["requires"] == {}


def test_create_format_json_and_deps_cpp_info():
    """
    Tests the ``conan create . -f json`` result, but ``cpp_info`` object only.

    The goal is to get something like:

    ```
    { ....
    'cpp_info': {'cmp1': {'bindirs': None,
                          'builddirs': None,
                          'cflags': None,
                          'cxxflags': None,
                          'defines': None,
                          'exelinkflags': None,
                          'frameworkdirs': None,
                          'frameworks': None,
                          'includedirs': None,
                          'libdirs': None,
                          'libs': ['libcmp1'],
                          'objects': None,
                          'properties': {'pkg_config_aliases': ['compo1_alias'],
                                         'pkg_config_name': 'compo1'},
                          'requires': None,
                          'resdirs': None,
                          'sharedlinkflags': None,
                          'srcdirs': None,
                          'sysroot': '/another/sysroot',
                          'system_libs': None},
                 'root': {'bindirs': ['bin'],
                          'builddirs': [],
                          'cflags': ['pkg_a_c_flag'],
                          'cxxflags': ['pkg_a_cxx_flag'],
                          'defines': ['pkg_onedefinition',
                                      'pkg_twodefinition'],
                          'exelinkflags': ['pkg_exe_link_flag'],
                          'frameworkdirs': ['framework/path/pkg'],
                          'frameworks': ['pkg_oneframework',
                                         'pkg_twoframework'],
                          'includedirs': ['path/includes/pkg',
                                          'include/path/pkg'],
                          'libdirs': ['lib/path/pkg'],
                          'libs': ['pkg'],
                          'objects': None,
                          'properties': {'pkg_config_aliases': ['pkg_alias1',
                                                                'pkg_alias2'],
                                         'pkg_config_name': 'pkg_other_name'},
                          'requires': None,
                          'resdirs': ['/path '
                                      'with '
                                      'spaces/.conan2/p/d15a235e212166d9/p/res'],
                          'sharedlinkflags': ['pkg_shared_link_flag'],
                          'srcdirs': None,
                          'sysroot': '/path/to/folder/pkg',
                          'system_libs': ['pkg_onesystemlib',
                                          'pkg_twosystemlib']}
    }}
    ```
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
    client.run("create . -f json")
    info = json.loads(client.stdout)
    nodes = info["graph"]["nodes"]
    hello_pkg_ref = 'hello/0.1#18d5440ae45afc4c36139a160ac071c7'
    pkg_pkg_ref = 'pkg/0.2#926714b5fb0a994f47ec37e071eba1da'
    hello_cpp_info = pkg_cpp_info = None
    for n in nodes:
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
    assert pkg_cpp_info['root']["properties"] == {'pkg_config_aliases': ['pkg_alias1', 'pkg_alias2'],
                                                  'pkg_config_name': 'pkg_other_name'}
    # component info
    assert pkg_cpp_info['cmp1']["libs"] == ['libcmp1']
    assert pkg_cpp_info['cmp1']["bindirs"][0].endswith("bin")  # Abs path /bin
    assert pkg_cpp_info['cmp1']["libdirs"][0].endswith("lib")  # Abs path /lib
    assert pkg_cpp_info['cmp1']["sysroot"] == "/another/sysroot"
    assert pkg_cpp_info['cmp1']["properties"] == {'pkg_config_aliases': ['compo1_alias'],
                                                  'pkg_config_name': 'compo1'}


def test_default_framework_dirs():

    conanfile = textwrap.dedent("""
    from conan import ConanFile


    class LibConan(ConanFile):
        name = "lib"
        version = "1.0"

        def package_info(self):
            self.output.warning("FRAMEWORKS: {}".format(self.cpp_info.frameworkdirs))""")
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    assert "FRAMEWORKS: []" in client.out


def test_default_framework_dirs_with_layout():

    conanfile = textwrap.dedent("""
    from conan import ConanFile


    class LibConan(ConanFile):
        name = "lib"
        version = "1.0"

        def layout(self):
            pass

        def package_info(self):
            self.output.warning("FRAMEWORKS: {}".format(self.cpp_info.frameworkdirs))""")
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    assert "FRAMEWORKS: []" in client.out


def test_defaults_in_components():
    """In Conan 2, declaring or not the layout has no influence in how cpp_info behaves. It was
       only 1.X"""
    lib_conan_file = textwrap.dedent("""
    from conan import ConanFile

    class LibConan(ConanFile):
        name = "lib"
        version = "1.0"

        def layout(self):
            pass

        def package_info(self):
            self.cpp_info.components["foo"].libs = ["foolib"]

    """)
    client = TestClient()
    client.save({"conanfile.py": lib_conan_file})
    client.run("create . ")

    consumer_conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Consumer(ConanFile):
            name = "consumer"
            version = "1.0"
            requires = "lib/1.0"

            def layout(self):
                pass

            def generate(self):
                cppinfo = self.dependencies["lib"].cpp_info
                components = cppinfo.components
                self.output.warning("BINDIRS: {}".format(cppinfo.bindirs))
                self.output.warning("LIBDIRS: {}".format(cppinfo.libdirs))
                self.output.warning("INCLUDEDIRS: {}".format(cppinfo.includedirs))
                self.output.warning("RESDIRS: {}".format(cppinfo.resdirs))
                self.output.warning("FOO LIBDIRS: {}".format(components["foo"].libdirs))
                self.output.warning("FOO INCLUDEDIRS: {}".format(components["foo"].includedirs))
                self.output.warning("FOO RESDIRS: {}".format(components["foo"].resdirs))

        """)

    client.save({"conanfile.py": consumer_conanfile})
    client.run("create . ")

    # The paths are absolute and the components have defaults
    # ".+" Check that there is a path, not only "lib"
    assert re.search(r"BINDIRS: \['.+bin'\]", str(client.out))
    assert re.search(r"LIBDIRS: \['.+lib'\]", str(client.out))
    assert re.search(r"INCLUDEDIRS: \['.+include'\]", str(client.out))
    assert "WARN: RES DIRS: []"
    assert re.search(r"WARN: FOO LIBDIRS: \['.+lib'\]", str(client.out))
    assert re.search(r"WARN: FOO INCLUDEDIRS: \['.+include'\]", str(client.out))
    assert "WARN: FOO RESDIRS: []" in client.out

    # The paths are absolute and the components have defaults
    # ".+" Check that there is a path, not only "lib"
    assert re.search("BINDIRS: \['.+bin'\]", str(client.out))
    assert re.search("LIBDIRS: \['.+lib'\]", str(client.out))
    assert re.search("INCLUDEDIRS: \['.+include'\]", str(client.out))
    assert "WARN: RES DIRS: []"
    assert bool(re.search("WARN: FOO LIBDIRS: \['.+lib'\]", str(client.out)))
    assert bool(re.search("WARN: FOO INCLUDEDIRS: \['.+include'\]", str(client.out)))
    assert "WARN: FOO RESDIRS: []" in client.out


def test_name_never():
    """ check that a package can be named equal to a build policy --build=never,
    because --build are now patterns
    Close https://github.com/conan-io/conan/issues/12430
    """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("never", "0.1")})
    c.run("create .")
    assert "never/0.1: Created package" in c.out
