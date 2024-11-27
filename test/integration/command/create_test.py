import json
import os
import re
import textwrap

from conans.model.recipe_ref import RecipeReference
from conan.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID, GenConanfile
from conans.util.files import load


def test_dependencies_order_matches_requires():
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


def test_create():
    client = TestClient()
    conanfile = textwrap.dedent("""
    from conan import ConanFile
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
    """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")
    assert "Profile host:\n[settings]" in client.out
    assert "pkg/0.1@lasote/testing: Generating the package" in client.out
    assert "Running system requirements!!" in client.out
    client.run('list -c *')
    assert "pkg/0.1@lasote/testing" in client.out

    # Create with only user will raise an error because of no name/version
    client.run("create conanfile.py --user=lasote --channel=testing", assert_error=True)
    assert "ERROR: conanfile didn't specify name" in client.out
    # Create with user but no channel should be valid
    client.run("create . --name=pkg --version=0.1 --user=lasote")
    assert "pkg/0.1@lasote:" in client.out


def test_error_create_name_version():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_name("hello").with_version("1.2")})
    client.run("create . --name=hello --version=1.2 --user=lasote --channel=stable")
    client.run("create . --name=pkg", assert_error=True)
    assert "ERROR: Package recipe with name pkg!=hello" in client.out
    client.run("create . --version=1.1", assert_error=True)
    assert "ERROR: Package recipe with version 1.1!=1.2" in client.out


def test_create_user_channel():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_name("pkg").with_version("0.1")})
    client.run("create . --user=lasote --channel=channel")
    assert "pkg/0.1@lasote/channel: Generating the package" in client.out
    client.run("list * -c")
    assert "pkg/0.1@lasote/channel" in client.out

    # test default without user and channel
    client.run("create . ")
    assert "pkg/0.1: Generating the package" in client.out


def test_create_in_subfolder():
    client = TestClient()
    client.save({"subfolder/conanfile.py": GenConanfile().with_name("pkg").with_version("0.1")})
    client.run("create subfolder --user=lasote --channel=channel")
    assert "pkg/0.1@lasote/channel: Generating the package" in client.out
    client.run("list * -c")
    assert "pkg/0.1@lasote/channel" in client.out


def test_create_in_subfolder_with_different_name():
    # Now with a different name
    client = TestClient()
    client.save({"subfolder/Custom.py": GenConanfile().with_name("pkg").with_version("0.1")})
    client.run("create subfolder/Custom.py --user=lasote --channel=channel")
    assert "pkg/0.1@lasote/channel: Generating the package" in client.out
    client.run("list * -c")
    assert "pkg/0.1@lasote/channel" in client.out


def test_create_test_package():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_name("pkg").with_version("0.1"),
                 "test_package/conanfile.py":
                     GenConanfile().with_test('self.output.info("TESTING!!!")')})
    client.run("create . --user=lasote --channel=testing")
    assert "pkg/0.1@lasote/testing: Generating the package" in client.out
    assert "pkg/0.1@lasote/testing (test package): TESTING!!!" in client.out


def test_create_skip_test_package():
    # Skip the test package stage if explicitly disabled with --test-folder=None
    # https://github.com/conan-io/conan/issues/2355
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_name("pkg").with_version("0.1"),
                 "test_package/conanfile.py":
                     GenConanfile().with_test('self.output.info("TESTING!!!")')})
    client.run("create . --user=lasote --channel=testing --test-folder=\"\"")
    assert "pkg/0.1@lasote/testing: Generating the package" in client.out
    assert "TESTING!!!" not in client.out


def test_create_package_requires():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=dep --version=0.1 --user=user --channel=channel")
    client.run("create . --name=other --version=1.0 --user=user --channel=channel")

    conanfile = GenConanfile().with_require("dep/0.1@user/channel")
    test_conanfile = textwrap.dedent("""
    from conan import ConanFile
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
    """)

    client.save({"conanfile.py": conanfile,
                 "test_package/conanfile.py": test_conanfile})

    client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")

    assert "pkg/0.1@lasote/testing (test package): build() " \
           "Requires: other/1.0@user/channel" in client.out
    assert "pkg/0.1@lasote/testing (test package): build() " \
           "Requires: pkg/0.1@lasote/testing" in client.out
    assert "pkg/0.1@lasote/testing (test package): build() cpp_info dep: other" in client.out
    assert "pkg/0.1@lasote/testing (test package): build() cpp_info dep: dep" in client.out
    assert "pkg/0.1@lasote/testing (test package): build() cpp_info dep: pkg" in client.out


def test_package_folder_build_error():
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

    assert "Build error" in client.out
    pref = client.get_latest_package_reference(ref, NO_SETTINGS_PACKAGE_ID)
    assert pref is None


def test_create_with_name_and_version():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run('create . --name=lib --version=1.0')
    assert "lib/1.0: Created package revision" in client.out


def test_create_with_only_user_channel():
    """This should be the recommended way and only from Conan 2.0"""
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_name("lib").with_version("1.0")})
    client.run('create . --user=user --channel=channel')
    assert "lib/1.0@user/channel: Created package revision" in client.out

    client.run('create . --user=user --channel=channel')
    assert "lib/1.0@user/channel: Created package revision" in client.out


def test_requires_without_user_channel():
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
    assert "hellobar/0.1: WARN: Hello, I'm hellobar" in client.out
    assert "consumer/1.0: Created package revision" in client.out


def test_conaninfo_contents_without_user_channel():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_name("hello").with_version("0.1")})
    client.run("create .")
    client.save({"conanfile.py": GenConanfile().with_name("bye").with_version("0.1")
                .with_require("hello/0.1")})
    client.run("create .")

    package_folder = client.created_layout().package()

    conaninfo = load(os.path.join(package_folder, "conaninfo.txt"))
    # The user and channel nor None nor "_/" appears in the conaninfo
    assert "None" not in conaninfo
    assert "_/" not in conaninfo
    assert "/_" not in conaninfo
    assert "[requires]\nhello/0.1\n" in conaninfo


def test_components_json_output():
    client = TestClient()
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
    client.save({"conanfile.py": conanfile})
    client.run("create . --format=json")
    data = json.loads(client.stdout)
    cpp_info_data = data["graph"]["nodes"]["1"]["cpp_info"]
    assert "libpkg1" in cpp_info_data["pkg1"]["libs"]
    assert cpp_info_data["pkg1"]["requires"] == []
    assert "libpkg2" in cpp_info_data["pkg2"]["libs"]
    assert cpp_info_data["pkg2"]["requires"] == ["pkg1"]


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

    # The & placeholder also works
    c.run("create pkg -s os=Linux --build=missing:&", assert_error=True)
    c.assert_listed_binary({"pkg/1.0": ("4c0c198b627f9af3e038af4da5e6b3ae205c2435", "Build")})
    c.assert_listed_binary({"dep/1.0": ("9a4eb3c8701508aa9458b1a73d0633783ecc2270", "Missing")})
    assert "ERROR: Missing prebuilt package for 'dep/1.0'" in c.out


def test_create_no_user_channel():
    """ test the --build=pattern and --build=missing:pattern syntax to build missing packages
     without user/channel
    """
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile(),
            "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep1/0.1", "dep2/0.1@user",
                                                                         "dep3/0.1@user/channel")})
    c.run("export dep --name=dep1 --version=0.1")
    c.run("export dep --name=dep2 --version=0.1 --user=user")
    c.run("export dep --name=dep3 --version=0.1 --user=user --channel=channel")

    # First test the ``--build=missing:pattern``
    c.run("create pkg --build=missing:*@", assert_error=True)
    c.assert_listed_binary({"dep1/0.1": (NO_SETTINGS_PACKAGE_ID, "Build"),
                            "dep2/0.1": (NO_SETTINGS_PACKAGE_ID, "Missing"),
                            "dep3/0.1": (NO_SETTINGS_PACKAGE_ID, "Missing")})
    c.run("create pkg --build=missing:!*@", assert_error=True)
    c.assert_listed_binary({"dep1/0.1": (NO_SETTINGS_PACKAGE_ID, "Missing"),
                            "dep2/0.1": (NO_SETTINGS_PACKAGE_ID, "Build"),
                            "dep3/0.1": (NO_SETTINGS_PACKAGE_ID, "Build")})

    # Now lets make sure they exist
    c.run("create pkg --build=missing")

    # Now test the --build=pattern
    c.run("create pkg --build=*@")
    c.assert_listed_binary({"dep1/0.1": (NO_SETTINGS_PACKAGE_ID, "Build"),
                            "dep2/0.1": (NO_SETTINGS_PACKAGE_ID, "Cache"),
                            "dep3/0.1": (NO_SETTINGS_PACKAGE_ID, "Cache")})
    # The --build=* needs to be said: "build all except those that have user/channel
    c.run("create pkg --build=* --build=!*@")
    c.assert_listed_binary({"dep1/0.1": (NO_SETTINGS_PACKAGE_ID, "Cache"),
                            "dep2/0.1": (NO_SETTINGS_PACKAGE_ID, "Build"),
                            "dep3/0.1": (NO_SETTINGS_PACKAGE_ID, "Build")})


def test_create_build_missing_negation():
    tc = TestClient(light=True)
    tc.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
             "lib/conanfile.py": GenConanfile("lib", "1.0").with_requires("dep/1.0"),
             "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_requires("lib/1.0")})

    tc.run("export dep")
    tc.run("export lib")
    tc.run("create pkg --build=missing:~dep/*", assert_error=True)

    tc.assert_listed_binary({"pkg/1.0": ("a72376edfbbdaf97c8608b5fda53cadebac46a20", "Build"),
                             "lib/1.0": ("abfcc78fa8242cabcd1e3d92896aa24808c789a3", "Build"),
                             "dep/1.0": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Missing")})

    tc.run("create pkg --build=missing:~dep/* --build=missing:~lib/*",
           assert_error=True)

    tc.assert_listed_binary({"pkg/1.0": ("a72376edfbbdaf97c8608b5fda53cadebac46a20", "Build"),
                             "lib/1.0": ("abfcc78fa8242cabcd1e3d92896aa24808c789a3", "Missing"),
                             "dep/1.0": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Missing")})


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
                 'dependencies': {'1': {'ref': 'hello/0.1', 'visible': 'True', ...}},
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

    for n in nodes.values():
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
    consumer_deps = {
        '1': {'ref': 'hello/0.1', 'run': False, 'libs': True, 'skip': False,
              'test': False, 'force': False, 'direct': True, 'build': False,
              'transitive_headers': None, 'transitive_libs': None, 'headers': True,
              'package_id_mode': None, 'visible': True},
        '2': {'ref': 'pkg/0.2', 'run': False, 'libs': True, 'skip': False, 'test': False,
              'force': False, 'direct': False, 'build': False, 'transitive_headers': None,
              'transitive_libs': None, 'headers': True, 'package_id_mode': None,
              'visible': True}
    }
    assert consumer_info["dependencies"] == consumer_deps
    # hello/0.1 pkg information
    assert hello_pkg_info["package_id"] == "8eba237c0fb239fcb7daa47979ab99258eaaa7d1"
    assert hello_pkg_info["prev"] == "d95380a07c35273509dfc36b26f6cec1"
    assert hello_pkg_info["settings"] == {}
    assert hello_pkg_info["options"] == {}
    hello_pkg_info_deps = {
        "2": {
            "ref": "pkg/0.2", "run": False, "libs": True, "skip": False, "test": False,
            "force": False, "direct": True, "build": False, "transitive_headers": None,
            "transitive_libs": None, "headers": True, "package_id_mode": "semver_mode",
            "visible": True
        }
    }
    assert hello_pkg_info["dependencies"] == hello_pkg_info_deps
    # pkg/0.2 pkg information
    assert pkg_pkg_info["package_id"] == "fb1439470288b15b2da269ed97b1a5f2f5d1f766"
    assert pkg_pkg_info["prev"] == "6949b0f89941d2a5994f9e6e4a89a331"
    assert pkg_pkg_info["author"] == 'John Doe'
    assert pkg_pkg_info["settings"] == {'build_type': 'Debug', 'compiler': 'gcc',
                                        'compiler.libcxx': 'libstdc++', 'compiler.version': '12'}
    assert pkg_pkg_info["options"] == {'fPIC': 'True', 'shared': 'False'}
    assert pkg_pkg_info["dependencies"] == {}


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
                          'dependencies': None,
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
                          'dependencies': None,
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
    assert re.search(r"BINDIRS: \['.+bin']", client.out)
    assert re.search(r"LIBDIRS: \['.+lib']", client.out)
    assert re.search(r"INCLUDEDIRS: \['.+include']", client.out)
    assert "WARN: RES DIRS: []"
    assert re.search(r"WARN: FOO LIBDIRS: \['.+lib']", client.out)
    assert re.search(r"WARN: FOO INCLUDEDIRS: \['.+include']", client.out)
    assert "WARN: FOO RESDIRS: []" in client.out

    # The paths are absolute and the components have defaults
    # ".+" Check that there is a path, not only "lib"
    assert re.search(r"BINDIRS: \['.+bin']", client.out)
    assert re.search(r"LIBDIRS: \['.+lib']", client.out)
    assert re.search(r"INCLUDEDIRS: \['.+include']", client.out)
    assert "WARN: RES DIRS: []"
    assert bool(re.search(r"WARN: FOO LIBDIRS: \['.+lib']", client.out))
    assert bool(re.search(r"WARN: FOO INCLUDEDIRS: \['.+include']", client.out))
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


def test_create_both_host_build_require():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("protobuf", "0.1").with_settings("build_type"),
            "test_package/conanfile.py": GenConanfile().with_build_requires("protobuf/0.1")
                                                       .with_test("pass")})
    c.run("create . -s:b build_type=Release -s:h build_type=Debug", assert_error=True)
    print(c.out)
    # The main "host" Debug binary will be correctly build
    c.assert_listed_binary({"protobuf/0.1": ("9e186f6d94c008b544af1569d1a6368d8339efc5", "Build")})
    # But test_package will fail because of the missing "tool_require" in Release
    c.assert_listed_binary({"protobuf/0.1": ("efa83b160a55b033c4ea706ddb980cd708e3ba1b", "Missing")},
                           build=True, test_package=True)

    c.run("remove * -c")  # make sure that previous binary is removed
    c.run("create . -s:b build_type=Release -s:h build_type=Debug --build-test=missing")
    c.assert_listed_binary({"protobuf/0.1": ("9e186f6d94c008b544af1569d1a6368d8339efc5", "Build")})
    # it used to fail, now it works and builds the test_package "tools_requires" in Release
    c.assert_listed_binary({"protobuf/0.1": ("9e186f6d94c008b544af1569d1a6368d8339efc5", "Cache")},
                           test_package=True)
    c.assert_listed_binary({"protobuf/0.1": ("efa83b160a55b033c4ea706ddb980cd708e3ba1b", "Build")},
                           build=True, test_package=True)

    # we can be more explicit about the current package only with "missing:protobuf/*"
    c.run("remove * -c")  # make sure that previous binary is removed
    c.run("create . -s:b build_type=Release -s:h build_type=Debug --build-test=missing:protobuf/*")
    c.assert_listed_binary({"protobuf/0.1": ("9e186f6d94c008b544af1569d1a6368d8339efc5", "Build")})
    # it used to fail, now it works and builds the test_package "tools_requires" in Release
    c.assert_listed_binary({"protobuf/0.1": ("efa83b160a55b033c4ea706ddb980cd708e3ba1b", "Build")},
                           build=True, test_package=True)


def test_python_requires_json_format():
    """Check python requires does not crash when calling conan create . --format=json
    See https://github.com/conan-io/conan/issues/14577"""
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pyreq", "1.0")
           .with_package_type("python-require")})
    c.run("create . --format=json", redirect_stdout="output.json")
    data = json.loads(load(os.path.join(c.current_folder, "output.json")))
    # There's a graph and the python requires is there
    assert len(data["graph"]["nodes"]["0"]["python_requires"]) == 1


def test_python_requires_with_test_package():
    c = TestClient()
    # Code comes from the docs
    conanfile = textwrap.dedent("""
    from conan import ConanFile

    def mynumber():
        return 42

    class PyReq(ConanFile):
        name = "pyreq"
        version = "1.0"
        package_type = "python-require"
    """)
    test_conanfile = textwrap.dedent("""
    from conan import ConanFile

    class Tool(ConanFile):
        def test(self):
            pyreq = self.python_requires["pyreq"].module
            mynumber = pyreq.mynumber()
            self.output.info("{}!!!".format(mynumber))
    """)
    c.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_conanfile})
    c.run("create .")
    # Ensure that creating a deps graph does not break the testing
    assert "pyreq/1.0 (test package): 42!!!" in c.out


def test_create_test_package_only_build():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1"),
            "test_package/conanfile.py": GenConanfile().with_test("self.output.info('TEST1!!!')"),
            "test_package2/conanfile.py": GenConanfile().with_test("self.output.info('TEST2!!!')")})
    # As it doesn't exist, it builds and test it
    c.run("create . -tm")
    assert "Testing the package" in c.out
    assert "TEST1!!!" in c.out
    # this will not create the binary, so it won't test it
    c.run("create . --build=missing --test-missing")
    assert "Testing the package" not in c.out
    assert "TEST" not in c.out
    c.run("create . -tf=test_package2 -tm")
    assert "Testing the package" in c.out
    assert "TEST2!!!" in c.out
    assert "TEST1!!!" not in c.out
    c.run("create . -tf=test_package2 --build=missing --test-missing")
    assert "Testing the package" not in c.out
    assert "TEST2!!!" not in c.out
    assert "TEST1!!!" not in c.out

    # error
    c.run("create . -tm -tf=", assert_error=True)
    assert '--test-folder="" is incompatible with --test-missing' in c.out


def test_create_test_package_only_build_python_require():
    c = TestClient()
    test = textwrap.dedent("""
        from conan import ConanFile

        class Tool(ConanFile):
            python_requires = "tested_reference_str"
            def test(self):
                self.output.info("TEST!!!!")
        """)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_package_type("python-require"),
            "test_package/conanfile.py": test})
    c.run("create .")
    assert "Testing the package" in c.out
    assert "pkg/0.1 (test package): TEST!!!" in c.out
    c.run("create . -tm")
    assert "Testing the package" in c.out
    assert "pkg/0.1 (test package): TEST!!!" in c.out
    c.run("create . -tm --build=missing")
    assert "Testing the package" in c.out
    assert "pkg/0.1 (test package): TEST!!!" in c.out
