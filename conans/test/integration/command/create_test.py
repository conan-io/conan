import json
import os
import re
import textwrap
import unittest
import pytest

from parameterized.parameterized import parameterized

from conans.client import tools
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID, GenConanfile
from conans.util.files import load


class CreateTest(unittest.TestCase):

    def test_dependencies_order_matches_requires(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
from conans.tools import save
import os
class Pkg(ConanFile):
    def package(self):
        save(os.path.join(self.package_folder, "include/file.h"), "//file")
    def package_info(self):
        self.cpp_info.libs = ["Lib%s"]
"""
        client.save({"conanfile.py": conanfile % "A"})
        client.run("create . PkgA/0.1@user/testing")
        client.save({"conanfile.py": conanfile % "B"})
        client.run("create . PkgB/0.1@user/testing")
        conanfile = """[requires]
PkgB/0.1@user/testing
PkgA/0.1@user/testing"""
        client.save({"conanfile.txt": conanfile}, clean_first=True)
        client.run("install . -g txt -g cmake")
        text = client.load("conanbuildinfo.txt")
        txt = ";".join(text.splitlines())
        self.assertIn("[libs];LibB;LibA", txt)
        cmake = client.load("conanbuildinfo.cmake")
        self.assertIn("set(CONAN_LIBS LibB LibA ${CONAN_LIBS})", cmake)

    def test_can_override_even_versions_with_build_metadata(self):
        # https://github.com/conan-io/conan/issues/5900

        client = TestClient()
        client.save({"conanfile.py":
                    GenConanfile().with_name("libcore").with_version("1.0+abc")})
        client.run("create .")
        client.save({"conanfile.py":
                    GenConanfile().with_name("libcore").with_version("1.0+xyz")})
        client.run("create .")

        client.save({"conanfile.py":
                    GenConanfile().with_name("intermediate").
                    with_version("1.0").with_require("libcore/1.0+abc")})
        client.run("create .")

        client.save({"conanfile.py":
                    GenConanfile().with_name("consumer").
                    with_version("1.0").with_require("intermediate/1.0").
                    with_require("libcore/1.0+xyz")})
        client.run("create .")
        self.assertIn("WARN: intermediate/1.0: requirement libcore/1.0+abc "
                      "overridden by consumer/1.0 to libcore/1.0+xyz", client.out)

    def test_transitive_same_name(self):
        # https://github.com/conan-io/conan/issues/1366
        client = TestClient()
        conanfile = GenConanfile().with_name("HelloBar").with_version("0.1")
        test_package = '''
from conans import ConanFile

class HelloTestConan(ConanFile):
    requires = "HelloBar/0.1@lasote/testing"
    def test(self):
        pass
'''
        client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_package})
        client.run("create . lasote/testing")
        self.assertIn("HelloBar/0.1@lasote/testing: Forced build from source",
                      client.out)
        conanfile = GenConanfile().with_name("Hello").with_version("0.1")\
                                  .with_require("HelloBar/0.1@lasote/testing")
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_package.replace("HelloBar", "Hello")})
        client.run("create . lasote/stable")
        self.assertNotIn("HelloBar/0.1@lasote/testing: Forced build from source",
                         client.out)

    @parameterized.expand([(True, ), (False, )])
    def test_keep_build(self, with_test):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class MyPkg(ConanFile):
                exports_sources = "*.h"
                def source(self):
                    self.output.info("mysource!!")
                def build(self):
                    self.output.info("mybuild!!")
                def package(self):
                    self.output.info("mypackage!!")
                    self.copy("*.h")
            """)
        if with_test:
            client.save({"conanfile.py": conanfile,
                         "header.h": "",
                         "test_package/conanfile.py": GenConanfile().with_test("pass")})
        else:
            client.save({"conanfile.py": conanfile,
                         "header.h": ""})

        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: mysource!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mybuild!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mypackage!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing package(): Packaged 1 '.h' file: header.h",
                      client.out)
        # keep the source
        client.save({"conanfile.py": conanfile + " "})
        client.run("create . Pkg/0.1@lasote/testing --keep-source")
        self.assertIn("A new conanfile.py version was exported", client.out)
        self.assertNotIn("Pkg/0.1@lasote/testing: mysource!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mybuild!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mypackage!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing package(): Packaged 1 '.h' file: header.h",
                      client.out)
        # keep build
        client.run("create . Pkg/0.1@lasote/testing --keep-build")
        self.assertIn("Pkg/0.1@lasote/testing: Won't be built as specified by --keep-build",
                      client.out)
        self.assertNotIn("Pkg/0.1@lasote/testing: mysource!!", client.out)
        self.assertNotIn("Pkg/0.1@lasote/testing: mybuild!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mypackage!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing package(): Packaged 1 '.h' file: header.h",
                      client.out)

        # Changes in the recipe again
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing --keep-build")
        # The source folder is removed, but not necessary, as it will reuse build
        self.assertNotIn("Pkg/0.1@lasote/testing: Removing 'source' folder", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Won't be built as specified by --keep-build",
                      client.out)
        self.assertNotIn("Pkg/0.1@lasote/testing: mysource!!", client.out)
        self.assertNotIn("Pkg/0.1@lasote/testing: mybuild!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: mypackage!!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing package(): Packaged 1 '.h' file: header.h",
                      client.out)

    def test_keep_build_error(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . Pkg/0.1@lasote/testing --keep-build", assert_error=True)
        self.assertIn("ERROR: --keep-build specified, but build folder not found", client.out)

    def test_keep_build_package_folder(self):
        """
        Package folder should be deleted always before a new conan create command, even with
        --keep-build
        """
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class MyPkg(ConanFile):
                exports_sources = "*.h", "*.cpp"
                def package(self):
                    self.copy("*.h")
            """)
        client.save({"conanfile.py": conanfile,
                     "header.h": "",
                     "source.cpp": ""})
        client.run("create . pkg/0.1@danimtb/testing")
        ref = ConanFileReference("pkg", "0.1", "danimtb", "testing")
        pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID)
        package_files = os.listdir(client.cache.package_layout(pref.ref).package(pref))
        self.assertIn("header.h", package_files)
        self.assertNotIn("source.cpp", package_files)
        client.save({"conanfile.py": conanfile.replace("self.copy(\"*.h\")",
                                                       "self.copy(\"*.cpp\")")})
        client.run("create . pkg/0.1@danimtb/testing -kb")
        package_files = os.listdir(client.cache.package_layout(pref.ref).package(pref))
        self.assertNotIn("header.h", package_files)
        self.assertIn("source.cpp", package_files)

    def test_create(self):
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
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
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Configuration:[settings]", "".join(str(client.out).splitlines()))
        self.assertIn("Pkg/0.1@lasote/testing: Generating the package", client.out)
        self.assertIn("Running system requirements!!", client.out)
        client.run("search")
        self.assertIn("Pkg/0.1@lasote/testing", client.out)

        # Create with only user will raise an error because of no name/version
        client.run("create conanfile.py lasote/testing", assert_error=True)
        self.assertIn("ERROR: conanfile didn't specify name", client.out)
        # Same with only user, (default testing)
        client.run("create . lasote", assert_error=True)
        self.assertIn("Invalid parameter 'lasote', specify the full reference or user/channel",
                      client.out)

    def test_create_name_command_line(self):
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
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
        self.assertIn("Pkg/0.1@lasote/testing: Generating the package", client.out)
        self.assertIn("Running system requirements!!", client.out)
        client.run("search")
        self.assertIn("Pkg/0.1@lasote/testing", client.out)

    def test_create_werror(self):
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
    pass
        """})
        client.run("export . LibA/0.1@user/channel")
        client.run("export conanfile.py LibA/0.2@user/channel")
        client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
    requires = "LibA/0.1@user/channel"
        """})
        client.run("export ./ LibB/0.1@user/channel")
        client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
    requires = "LibA/0.2@user/channel"
        """})
        client.run("export . LibC/0.1@user/channel")
        client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
    requires = "LibB/0.1@user/channel", "LibC/0.1@user/channel"
        """})
        client.run("create ./conanfile.py Consumer/0.1@lasote/testing", assert_error=True)
        self.assertIn("ERROR: Conflict in LibC/0.1@user/channel",
                      client.out)

    def test_error_create_name_version(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("Hello").with_version("1.2")})
        client.run("create . Hello/1.2@lasote/stable")
        client.run("create ./ Pkg/1.2@lasote/stable", assert_error=True)
        self.assertIn("ERROR: Package recipe with name Pkg!=Hello", client.out)
        client.run("create . Hello/1.1@lasote/stable", assert_error=True)
        self.assertIn("ERROR: Package recipe with version 1.1!=1.2", client.out)

    def test_create_user_channel(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("Pkg").with_version("0.1")})
        client.run("create . lasote/channel")
        self.assertIn("Pkg/0.1@lasote/channel: Generating the package", client.out)
        client.run("search")
        self.assertIn("Pkg/0.1@lasote/channel", client.out)

        client.run("create . lasote", assert_error=True)  # testing default
        self.assertIn("Invalid parameter 'lasote', specify the full reference or user/channel",
                      client.out)

    def test_create_in_subfolder(self):
        client = TestClient()
        client.save({"subfolder/conanfile.py": GenConanfile().with_name("Pkg").with_version("0.1")})
        client.run("create subfolder lasote/channel")
        self.assertIn("Pkg/0.1@lasote/channel: Generating the package", client.out)
        client.run("search")
        self.assertIn("Pkg/0.1@lasote/channel", client.out)

    def test_create_in_subfolder_with_different_name(self):
        # Now with a different name
        client = TestClient()
        client.save({"subfolder/Custom.py": GenConanfile().with_name("Pkg").with_version("0.1")})
        client.run("create subfolder/Custom.py lasote/channel")
        self.assertIn("Pkg/0.1@lasote/channel: Generating the package", client.out)
        client.run("search")
        self.assertIn("Pkg/0.1@lasote/channel", client.out)

    def test_create_test_package(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("Pkg").with_version("0.1"),
                     "test_package/conanfile.py":
                         GenConanfile().with_test('self.output.info("TESTING!!!")')})
        client.run("create . lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: Generating the package", client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): TESTING!!!", client.out)

    def test_create_skip_test_package(self):
        # Skip the test package stage if explicitly disabled with --test-folder=None
        # https://github.com/conan-io/conan/issues/2355
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("Pkg").with_version("0.1"),
                     "test_package/conanfile.py":
                         GenConanfile().with_test('self.output.info("TESTING!!!")')})
        client.run("create . lasote/testing --test-folder=None")
        self.assertIn("Pkg/0.1@lasote/testing: Generating the package", client.out)
        self.assertNotIn("TESTING!!!", client.out)

    def test_create_package_requires(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . Dep/0.1@user/channel")
        client.run("create . Other/1.0@user/channel")

        conanfile = GenConanfile().with_require("Dep/0.1@user/channel")
        test_conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    requires = "Other/1.0@user/channel"
    def build(self):
        for r in self.requires.values():
            self.output.info("build() Requires: %s" % str(r.ref))
        import os
        for dep in self.deps_cpp_info.deps:
            self.output.info("build() cpp_info dep: %s" % dep)
        self.output.info("build() cpp_info: %s"
                         % os.path.basename(self.deps_cpp_info["Pkg"].includedirs[0]))
        self.output.info("build() cpp_info: %s"
                         % os.path.basename(self.deps_cpp_info["Dep"].includedirs[0]))
    def test(self):
        pass
        """

        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile})

        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing (test package): build() cpp_info: include",
                      client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): build() "
                      "Requires: Other/1.0@user/channel", client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): build() "
                      "Requires: Pkg/0.1@lasote/testing", client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): build() cpp_info dep: Other",
                      client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): build() cpp_info dep: Dep",
                      client.out)
        self.assertIn("Pkg/0.1@lasote/testing (test package): build() cpp_info dep: Pkg",
                      client.out)

    def test_build_policy(self):
        # https://github.com/conan-io/conan/issues/1956
        client = TestClient()
        conanfile = str(GenConanfile()) + '\n    build_policy = "always"'
        test_package = GenConanfile().with_test("pass")
        client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_package})
        client.run("create . Bar/0.1@user/stable")
        self.assertIn("Bar/0.1@user/stable: Forced build from source", client.out)

        # Transitive too
        client.save({"conanfile.py": GenConanfile().with_require("Bar/0.1@user/stable")})
        client.run("create . pkg/0.1@user/stable")
        self.assertIn("Bar/0.1@user/stable: Forced build from source", client.out)

    def test_build_folder_handling(self):
        conanfile = GenConanfile().with_name("Hello").with_version("0.1")
        test_conanfile = GenConanfile().with_test("pass")
        client = TestClient()
        default_build_dir = os.path.join(client.current_folder, "test_package", "build")

        # Test the default behavior.
        client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_conanfile},
                    clean_first=True)
        client.run("create . lasote/stable")
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
        with tools.environment_append({"CONAN_TEMP_TEST_FOLDER": "True"}):
            client.run("create . lasote/stable")
        self.assertFalse(os.path.exists(default_build_dir))

        # # Test if using a temporary test folder can be enabled via the config file.
        client.run('config set general.temp_test_folder=True')
        client.run("create . lasote/stable")
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
            from conans import ConanFile

            class MyPkg(ConanFile):

                def build(self):
                    raise ConanException("Build error")
            """)
        client.save({"conanfile.py": conanfile})
        ref = ConanFileReference("pkg", "0.1", "danimtb", "testing")
        pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID, None)
        client.run("create . %s" % ref.full_str(), assert_error=True)
        self.assertIn("Build error", client.out)
        package_folder = client.cache.package_layout(pref.ref).package(pref)
        self.assertFalse(os.path.exists(package_folder))

    def test_create_with_name_and_version(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run('create . lib/1.0@')
        self.assertIn("lib/1.0: Created package revision", client.out)

    def test_create_with_only_user_channel(self):
        """This should be the recommended way and only from Conan 2.0"""
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("lib").with_version("1.0")})
        client.run('create . @user/channel')
        self.assertIn("lib/1.0@user/channel: Created package revision", client.out)

        client.run('create . user/channel')
        self.assertIn("lib/1.0@user/channel: Created package revision", client.out)

    def test_requires_without_user_channel(self):
        client = TestClient()
        conanfile = textwrap.dedent('''
            from conans import ConanFile

            class HelloConan(ConanFile):
                name = "HelloBar"
                version = "0.1"

                def package_info(self):
                    self.output.warn("Hello, I'm HelloBar")
            ''')

        client.save({"conanfile.py": conanfile})
        client.run("create .")

        client.save({"conanfile.py": GenConanfile().with_require("HelloBar/0.1")})
        client.run("create . consumer/1.0@")
        self.assertIn("HelloBar/0.1: WARN: Hello, I'm HelloBar", client.out)
        self.assertIn("consumer/1.0: Created package revision", client.out)

    def test_conaninfo_contents_without_user_channel(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("Hello").with_version("0.1")})
        client.run("create .")
        client.save({"conanfile.py": GenConanfile().with_name("Bye").with_version("0.1")
                                                   .with_require("Hello/0.1")})
        client.run("create .")

        ref = ConanFileReference.loads("Bye/0.1")
        packages_folder = client.cache.package_layout(ref).packages()
        p_folder = os.path.join(packages_folder, os.listdir(packages_folder)[0])
        conaninfo = load(os.path.join(p_folder, "conaninfo.txt"))
        # The user and channel nor None nor "_/" appears in the conaninfo
        self.assertNotIn("None", conaninfo)
        self.assertNotIn("_/", conaninfo)
        self.assertNotIn("/_", conaninfo)
        self.assertIn("[full_requires]\n    Hello/0.1:{}\n".format(NO_SETTINGS_PACKAGE_ID),
                      conaninfo)

    def test_compoents_json_output(self):
        self.client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

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


def test_default_framework_dirs():

    conanfile = textwrap.dedent("""
    from conans import ConanFile, CMake, tools


    class LibConan(ConanFile):
        name = "lib"
        version = "1.0"

        def package_info(self):
            self.output.warn("FRAMEWORKS: {}".format(self.cpp_info.frameworkdirs))""")
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    assert "FRAMEWORKS: ['Frameworks']" in client.out


def test_default_framework_dirs_with_layout():

    conanfile = textwrap.dedent("""
    from conans import ConanFile, CMake, tools


    class LibConan(ConanFile):
        name = "lib"
        version = "1.0"

        def layout(self):
            pass

        def package_info(self):
            self.output.warn("FRAMEWORKS: {}".format(self.cpp_info.frameworkdirs))""")
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    assert "FRAMEWORKS: []" in client.out


@pytest.mark.parametrize("with_layout", [True, False])
def test_defaults_in_components_without_layout(with_layout):
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
    if not with_layout:
        lib_conan_file = lib_conan_file.replace("def layout(", "def potato(")
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
                if hasattr(self, "layout"):
                    cppinfo = self.dependencies["lib"].cpp_info
                else:
                    cppinfo = dict(self.deps_cpp_info.dependencies)["lib"]

                components = cppinfo.components
                self.output.warn("BINDIRS: {}".format(cppinfo.bindirs))
                self.output.warn("LIBDIRS: {}".format(cppinfo.libdirs))
                self.output.warn("INCLUDEDIRS: {}".format(cppinfo.includedirs))
                self.output.warn("RESDIRS: {}".format(cppinfo.resdirs))
                self.output.warn("FOO LIBDIRS: {}".format(components["foo"].libdirs))
                self.output.warn("FOO INCLUDEDIRS: {}".format(components["foo"].includedirs))
                self.output.warn("FOO RESDIRS: {}".format(components["foo"].resdirs))

        """)

    if not with_layout:
        consumer_conanfile = consumer_conanfile.replace("def layout(", "def potato(")

    client.save({"conanfile.py": consumer_conanfile})
    client.run("create . ")

    if with_layout:
        # The paths are absolute and the components have defaults
        # ".+" Check that there is a path, not only "lib"
        assert re.search("BINDIRS: \['.+bin'\]", str(client.out))
        assert re.search("LIBDIRS: \['.+lib'\]", str(client.out))
        assert re.search("INCLUDEDIRS: \['.+include'\]", str(client.out))
        assert "WARN: RES DIRS: []"
        assert bool(re.search("WARN: FOO LIBDIRS: \['.+lib'\]", str(client.out))) is with_layout
        assert bool(re.search("WARN: FOO INCLUDEDIRS: \['.+include'\]", str(client.out))) is with_layout
        assert "WARN: FOO RESDIRS: []" in client.out
    else:
        # The paths are not absolute and the components have defaults
        assert "BINDIRS: ['bin']" in client.out
        assert "LIBDIRS: ['lib']" in client.out
        assert "INCLUDEDIRS: ['include']" in client.out
        assert "FOO LIBDIRS: ['lib']" in client.out
        assert "FOO INCLUDEDIRS: ['include']" in client.out
        assert "FOO RESDIRS: ['res']" in client.out


def test_create_keep_build_sets_generators_folder_even_with_cmake_layout_defined():
    """
    Issue related: https://github.com/conan-io/conan/issues/11785
    """
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.cmake import cmake_layout

    class LibConan(ConanFile):
        settings = 'os', 'arch', 'compiler', 'build_type'
        name = "lib"
        version = "1.0"

        def layout(self):
            cmake_layout(self)

        def package(self):
            self.output.info("GENERATORS FOLDER: {}".format(self.generators_folder))
    """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . -s build_type=Release")
    client.run("create -kb . -s build_type=Release")
    # self.generators_folder should be not None when -kb is used
    assert re.search(r"GENERATORS FOLDER: .*generators", str(client.out))
