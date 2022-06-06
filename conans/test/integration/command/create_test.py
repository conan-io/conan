import json
import os
import textwrap
import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID, GenConanfile
from conans.util.files import load, save


class CreateTest(unittest.TestCase):

    def test_dependencies_order_matches_requires(self):
        client = TestClient()
        save(client.cache.default_profile_path, "")
        save(client.cache.settings_path, "build_type: [Release, Debug]\narch: [x86]")
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

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_create(self):
        client = TestClient()
        client.save({"conanfile.py": """from conan import ConanFile
class MyPkg(ConanFile):
    def source(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def configure(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def requirements(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def build(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def package(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def package_info(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def system_requirements(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
        self.output.info("Running system requirements!!")
"""})
        client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing")
        self.assertIn("Configuration (profile_host):[settings]",
                      "".join(str(client.out).splitlines()))
        self.assertIn("pkg/0.1@lasote/testing: Generating the package", client.out)
        self.assertIn("Running system requirements!!", client.out)
        client.run("search")
        self.assertIn("pkg/0.1@lasote/testing", client.out)

        # Create with only user will raise an error because of no name/version
        client.run("create conanfile.py --use=lasote --channel=testing", assert_error=True)
        self.assertIn("ERROR: conanfile didn't specify name", client.out)
        # Same with only user, (default testing)
        client.run("create . --user=lasote")
        assert "pkg/0.1@lasote:" in client.out

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_create_name_command_line(self):
        client = TestClient()
        client.save({"conanfile.py": """from conan import ConanFile
class MyPkg(ConanFile):
    name = "Pkg"
    def source(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def configure(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def requirements(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def build(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def package(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def package_info(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def system_requirements(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
        self.output.info("Running system requirements!!")
"""})
        client.run("create . 0.1@lasote/testing")
        self.assertIn("pkg/0.1@lasote/testing: Generating the package", client.out)
        self.assertIn("Running system requirements!!", client.out)
        client.run("search")
        self.assertIn("pkg/0.1@lasote/testing", client.out)

    def test_error_create_name_version(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("hello").with_version("1.2")})
        client.run("create . --name=hello --version=1.2 --user=lasote --channel=stable")
        client.run("create . --name=pkg", assert_error=True)
        self.assertIn("ERROR: Package recipe with name pkg!=hello", client.out)
        client.run("create . --version=1.1", assert_error=True)
        self.assertIn("ERROR: Package recipe with version 1.1!=1.2", client.out)

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_create_user_channel(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("pkg").with_version("0.1")})
        client.run("create . --user=lasote --channel=channel")
        self.assertIn("pkg/0.1@lasote/channel: Generating the package", client.out)
        client.run("search")
        self.assertIn("pkg/0.1@lasote/channel", client.out)

        client.run("create . lasote", assert_error=True)  # testing default
        self.assertIn("Invalid parameter 'lasote', specify the full reference or user/channel",
                      client.out)

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_create_in_subfolder(self):
        client = TestClient()
        client.save({"subfolder/conanfile.py": GenConanfile().with_name("pkg").with_version("0.1")})
        client.run("create subfolder lasote/channel")
        self.assertIn("pkg/0.1@lasote/channel: Generating the package", client.out)
        client.run("search")
        self.assertIn("pkg/0.1@lasote/channel", client.out)

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_create_in_subfolder_with_different_name(self):
        # Now with a different name
        client = TestClient()
        client.save({"subfolder/Custom.py": GenConanfile().with_name("pkg").with_version("0.1")})
        client.run("create subfolder/Custom.py lasote/channel")
        self.assertIn("pkg/0.1@lasote/channel: Generating the package", client.out)
        client.run("search")
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
        client.run("create . --user=lasote --channel=testing --test-folder=None")
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

    def test_build_policy(self):
        # https://github.com/conan-io/conan/issues/1956
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_class_attribute('build_policy = "always"')})
        client.run("create . --name=bar --version=0.1")
        self.assertIn("bar/0.1: Forced build from source", client.out)

        # Transitive too
        client.save({"conanfile.py": GenConanfile().with_require("bar/0.1@")})
        client.run("create . --name=pkg --version=0.1")
        self.assertIn("bar/0.1: Forced build from source", client.out)

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

    @pytest.mark.xfail(reason="--json output has been disabled")
    def test_compoents_json_output(self):
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
        self.client.run("create . --json jsonfile.json")
        path = os.path.join(self.client.current_folder, "jsonfile.json")
        content = self.client.load(path)
        data = json.loads(content)
        cpp_info_data = data["installed"][0]["packages"][0]["cpp_info"]
        self.assertIn("libpkg1", cpp_info_data["components"]["pkg1"]["libs"])
        self.assertNotIn("requires", cpp_info_data["components"]["pkg1"])
        self.assertIn("libpkg2", cpp_info_data["components"]["pkg2"]["libs"])
        self.assertListEqual(["pkg1"], cpp_info_data["components"]["pkg2"]["requires"])


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
            "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep/1.0")})
    c.run("create dep -s os=Windows")
    c.run("create pkg -s os=Windows")
    c.assert_listed_binary({"pkg/1.0": ("abfcc78fa8242cabcd1e3d92896aa24808c789a3", "Build")})
    # Now avoid rebuilding
    c.run("create pkg -s os=Windows --build=missing:pkg")
    c.assert_listed_binary({"pkg/1.0": ("abfcc78fa8242cabcd1e3d92896aa24808c789a3", "Cache")})
    assert "Calling build()" not in c.out
    # but dependency without binary will fail
    c.run("create pkg -s os=Linux --build=missing:pkg", assert_error=True)
    c.assert_listed_binary({"pkg/1.0": ("abfcc78fa8242cabcd1e3d92896aa24808c789a3", "Cache")})
    assert "ERROR: Missing prebuilt package for 'dep/1.0'" in c.out
