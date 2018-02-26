import unittest
import platform
import os

from conans.test.utils.tools import TestClient, TestServer
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE, CONANINFO
from conans.model.info import ConanInfo
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.paths import CONANFILE_TXT
from conans.client.conf.detect import detected_os
from conans.util.files import load, mkdir, rmdir


class InstallTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        self.settings = ("-s os=Windows -s compiler='Visual Studio' -s compiler.version=12 "
                         "-s arch=x86 -s compiler.runtime=MD")

    def install_transitive_pattern_test(self):
        # Make sure a simple conan install doesn't fire package_info() so self.package_folder breaks
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
    options = {"shared": [True, False, "header"]}
    default_options = "shared=False"
    def package_info(self):
        self.output.info("PKG OPTION: %s" % self.options.shared)
"""})
        client.run("create . Pkg/0.1@user/testing -o shared=True")
        self.assertIn("Pkg/0.1@user/testing: PKG OPTION: True", client.out)
        client.save({"conanfile.py": """from conans import ConanFile
class Pkg(ConanFile):
    requires = "Pkg/0.1@user/testing"
    options = {"shared": [True, False, "header"]}
    default_options = "shared=False"
    def package_info(self):
        self.output.info("PKG2 OPTION: %s" % self.options.shared)
"""})

        client.run("create . Pkg2/0.1@user/testing -o *:shared=True")
        self.assertIn("Pkg/0.1@user/testing: PKG OPTION: True", client.out)
        self.assertIn("Pkg2/0.1@user/testing: PKG2 OPTION: True", client.out)
        client.run("install Pkg2/0.1@user/testing -o *:shared=True")
        self.assertIn("Pkg/0.1@user/testing: PKG OPTION: True", client.out)
        self.assertIn("Pkg2/0.1@user/testing: PKG2 OPTION: True", client.out)
        # Priority of non-scoped options
        client.run("create . Pkg2/0.1@user/testing -o shared=header -o *:shared=True")
        self.assertIn("Pkg/0.1@user/testing: PKG OPTION: True", client.out)
        self.assertIn("Pkg2/0.1@user/testing: PKG2 OPTION: header", client.out)
        client.run("install Pkg2/0.1@user/testing -o shared=header -o *:shared=True")
        self.assertIn("Pkg/0.1@user/testing: PKG OPTION: True", client.out)
        self.assertIn("Pkg2/0.1@user/testing: PKG2 OPTION: header", client.out)
        # Prevalence of exact named option
        client.run("create . Pkg2/0.1@user/testing -o *:shared=True -o Pkg2:shared=header")
        self.assertIn("Pkg/0.1@user/testing: PKG OPTION: True", client.out)
        self.assertIn("Pkg2/0.1@user/testing: PKG2 OPTION: header", client.out)
        client.run("install Pkg2/0.1@user/testing -o *:shared=True -o Pkg2:shared=header")
        self.assertIn("Pkg/0.1@user/testing: PKG OPTION: True", client.out)
        self.assertIn("Pkg2/0.1@user/testing: PKG2 OPTION: header", client.out)
        # Prevalence of exact named option reverse
        client.run("create . Pkg2/0.1@user/testing -o *:shared=True -o Pkg:shared=header --build=missing")
        self.assertIn("Pkg/0.1@user/testing: Calling build()", client.out)
        self.assertIn("Pkg/0.1@user/testing: PKG OPTION: header", client.out)
        self.assertIn("Pkg2/0.1@user/testing: PKG2 OPTION: True", client.out)
        client.run("install Pkg2/0.1@user/testing -o *:shared=True -o Pkg:shared=header")
        self.assertIn("Pkg/0.1@user/testing: PKG OPTION: header", client.out)
        self.assertIn("Pkg2/0.1@user/testing: PKG2 OPTION: True", client.out)
        # Prevalence of alphabetical pattern
        client.run("create . Pkg2/0.1@user/testing -o *:shared=True -o Pkg2*:shared=header")
        self.assertIn("Pkg/0.1@user/testing: PKG OPTION: True", client.out)
        self.assertIn("Pkg2/0.1@user/testing: PKG2 OPTION: header", client.out)
        client.run("install Pkg2/0.1@user/testing -o *:shared=True -o Pkg2*:shared=header")
        self.assertIn("Pkg/0.1@user/testing: PKG OPTION: True", client.out)
        self.assertIn("Pkg2/0.1@user/testing: PKG2 OPTION: header", client.out)
        # Prevalence of alphabetical pattern, opposite order
        client.run("create . Pkg2/0.1@user/testing -o Pkg2*:shared=header -o *:shared=True")
        self.assertIn("Pkg/0.1@user/testing: PKG OPTION: True", client.out)
        self.assertIn("Pkg2/0.1@user/testing: PKG2 OPTION: header", client.out)
        client.run("install Pkg2/0.1@user/testing -o Pkg2*:shared=header -o *:shared=True")
        self.assertIn("Pkg/0.1@user/testing: PKG OPTION: True", client.out)
        self.assertIn("Pkg2/0.1@user/testing: PKG2 OPTION: header", client.out)
        # Prevalence and override of alphabetical pattern
        client.run("create . Pkg2/0.1@user/testing -o *:shared=True -o Pkg*:shared=header")
        self.assertIn("Pkg/0.1@user/testing: PKG OPTION: header", client.out)
        self.assertIn("Pkg2/0.1@user/testing: PKG2 OPTION: header", client.out)
        client.run("install Pkg2/0.1@user/testing -o *:shared=True -o Pkg*:shared=header")
        self.assertIn("Pkg/0.1@user/testing: PKG OPTION: header", client.out)
        self.assertIn("Pkg2/0.1@user/testing: PKG2 OPTION: header", client.out)

    def install_package_folder_test(self):
        # Make sure a simple conan install doesn't fire package_info() so self.package_folder breaks
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
import os
class Pkg(ConanFile):
    def package_info(self):
        self.dummy_doesnt_exist_not_break
        self.output.info("Hello")
        self.env_info.PATH = os.path.join(self.package_folder, "bin")
"""})
        client.run("install .")
        self.assertNotIn("Hello", client.out)
        self.assertIn("PROJECT: Generated conaninfo.txt", client.out)

    def _create(self, number, version, deps=None, export=True, no_config=False, settings=None):
        files = cpp_hello_conan_files(number, version, deps, build=False, config=not no_config,
                                      settings=settings)

        self.client.save(files, clean_first=True)
        if export:
            self.client.run("export . lasote/stable")

    def install_error_never_test(self):
        self._create("Hello0", "0.1", export=False)
        error = self.client.run("install . --build never --build missing", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: --build=never not compatible with other options",
                      self.client.user_io.out)
        error = self.client.run("install conanfile.py --build never --build Hello", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: --build=never not compatible with other options",
                      self.client.user_io.out)
        error = self.client.run("install ./conanfile.py --build never --build outdated", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: --build=never not compatible with other options",
                      self.client.user_io.out)

    def install_combined_test(self):
        self._create("Hello0", "0.1")
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False)
        self.client.run("install . %s --build=missing" % (self.settings))

        self.client.run("install . %s --build=missing --build Hello1" % (self.settings))
        self.assertIn("Hello0/0.1@lasote/stable: Already installed!",
                      self.client.user_io.out)
        self.assertIn("Hello1/0.1@lasote/stable: WARN: Forced build from source",
                      self.client.user_io.out)

    def install_transitive_cache_test(self):
        self._create("Hello0", "0.1")
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"])
        self.client.run("install Hello2/0.1@lasote/stable %s --build=missing" % (self.settings))
        self.assertIn("Hello0/0.1@lasote/stable: Generating the package",
                      self.client.user_io.out)
        self.assertIn("Hello1/0.1@lasote/stable: Generating the package",
                      self.client.user_io.out)
        self.assertIn("Hello2/0.1@lasote/stable: Generating the package",
                      self.client.user_io.out)

    def partials_test(self):
        self._create("Hello0", "0.1")
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False)

        self.client.run("install . %s --build=missing" % self.settings)

        self.client.run("install ./ %s --build=Bye" % self.settings)
        self.assertIn("No package matching 'Bye' pattern", self.client.user_io.out)

        for package in ["Hello0", "Hello1"]:
            self.client.run("install . %s --build=%s" % (self.settings, package))
            self.assertNotIn("No package matching", self.client.user_io.out)

    def reuse_test(self):
        self._create("Hello0", "0.1")
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False)

        for lang, id0, id1 in [(0, "2e38bbc2c3ef1425197c8e2ffa8532894c347d26",
                                   "44671ecdd9c606eb7166f2197ab50be8d36a3c3b"),
                               (1, "8b964e421a5b7e48b7bc19b94782672be126be8b",
                                   "3eeab577a3134fa3afdcd82881751789ec48e08f")]:

            self.client.run("install . -o language=%d %s --build missing" % (lang, self.settings))
            info_path = os.path.join(self.client.current_folder, CONANINFO)
            conan_info = ConanInfo.load_file(info_path)
            self.assertEqual("arch=x86\n"
                             "compiler=Visual Studio\n"
                             "compiler.runtime=MD\n"
                             "compiler.version=12\n"
                             "os=Windows",
                             conan_info.settings.dumps())
            self.assertEqual("language=%s\nstatic=True" % lang, conan_info.options.dumps())
            conan_ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")

            hello0 = self.client.paths.package(PackageReference(conan_ref, id0))
            hello0_info = os.path.join(hello0, CONANINFO)
            hello0_conan_info = ConanInfo.load_file(hello0_info)
            self.assertEqual(lang, hello0_conan_info.options.language)

            package_ref1 = PackageReference(ConanFileReference.loads("Hello1/0.1@lasote/stable"),
                                            id1)
            hello1 = self.client.paths.package(package_ref1)
            hello1_info = os.path.join(hello1, CONANINFO)
            hello1_conan_info = ConanInfo.load_file(hello1_info)
            self.assertEqual(lang, hello1_conan_info.options.language)

    def upper_option_test(self):
        self._create("Hello0", "0.1", no_config=True)
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"], no_config=True)
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False, no_config=True)

        self.client.run("install conanfile.py -o Hello2:language=1 -o Hello1:language=0 -o Hello0:language=1 %s"
                        " --build missing" % self.settings)
        info_path = os.path.join(self.client.current_folder, CONANINFO)
        conan_info = ConanInfo.load_file(info_path)
        self.assertEqual("language=1\nstatic=True", conan_info.options.dumps())
        conan_ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")

        hello0 = self.client.paths.package(PackageReference(conan_ref,
                                           "8b964e421a5b7e48b7bc19b94782672be126be8b"))
        hello0_info = os.path.join(hello0, CONANINFO)
        hello0_conan_info = ConanInfo.load_file(hello0_info)
        self.assertEqual(1, hello0_conan_info.options.language)

        package_ref1 = PackageReference(ConanFileReference.loads("Hello1/0.1@lasote/stable"),
                                        "44671ecdd9c606eb7166f2197ab50be8d36a3c3b")
        hello1 = self.client.paths.package(package_ref1)
        hello1_info = os.path.join(hello1, CONANINFO)
        hello1_conan_info = ConanInfo.load_file(hello1_info)
        self.assertEqual(0, hello1_conan_info.options.language)

    def inverse_upper_option_test(self):
        self._create("Hello0", "0.1", no_config=True)
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"], no_config=True)
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False, no_config=True)

        self.client.run("install . -o language=0 -o Hello1:language=1 -o Hello0:language=0 %s "
                        "--build missing" % self.settings)
        info_path = os.path.join(self.client.current_folder, CONANINFO)

        conan_info = ConanInfo.load_file(info_path)

        self.assertEqual("language=0\nstatic=True", conan_info.options.dumps())
        conan_ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")

        hello0 = self.client.paths.package(PackageReference(conan_ref,
                                           "2e38bbc2c3ef1425197c8e2ffa8532894c347d26"))
        hello0_info = os.path.join(hello0, CONANINFO)
        hello0_conan_info = ConanInfo.load_file(hello0_info)
        self.assertEqual("language=0\nstatic=True", hello0_conan_info.options.dumps())

        package_ref1 = PackageReference(ConanFileReference.loads("Hello1/0.1@lasote/stable"),
                                        "3eeab577a3134fa3afdcd82881751789ec48e08f")
        hello1 = self.client.paths.package(package_ref1)
        hello1_info = os.path.join(hello1, CONANINFO)
        hello1_conan_info = ConanInfo.load_file(hello1_info)
        self.assertEqual("language=1\nstatic=True", hello1_conan_info.options.dumps())

    def upper_option_txt_test(self):
        self._create("Hello0", "0.1", no_config=True)
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"], no_config=True)

        files = cpp_hello_conan_files("Hello2", "0.1", ["Hello1/0.1@lasote/stable"])
        files.pop(CONANFILE)
        files[CONANFILE_TXT] = """[requires]
        Hello1/0.1@lasote/stable

        [options]
        Hello0:language=1
        Hello1:language=0
        """
        self.client.save(files, clean_first=True)

        self.client.run("install . %s --build missing" % self.settings)
        info_path = os.path.join(self.client.current_folder, CONANINFO)
        conan_info = ConanInfo.load_file(info_path)
        self.assertEqual("", conan_info.options.dumps())
        conan_ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")

        hello0 = self.client.paths.package(PackageReference(conan_ref,
                                           "8b964e421a5b7e48b7bc19b94782672be126be8b"))
        hello0_info = os.path.join(hello0, CONANINFO)
        hello0_conan_info = ConanInfo.load_file(hello0_info)
        self.assertEqual(1, hello0_conan_info.options.language)

        package_ref1 = PackageReference(ConanFileReference.loads("Hello1/0.1@lasote/stable"),
                                        "44671ecdd9c606eb7166f2197ab50be8d36a3c3b")
        hello1 = self.client.paths.package(package_ref1)
        hello1_info = os.path.join(hello1, CONANINFO)
        hello1_conan_info = ConanInfo.load_file(hello1_info)
        self.assertEqual(0, hello1_conan_info.options.language)

    def change_option_txt_test(self):
        self._create("Hello0", "0.1")

        client = TestClient(base_folder=self.client.base_folder)
        files = {CONANFILE_TXT: """[requires]
        Hello0/0.1@lasote/stable

        [options]
        Hello0:language=1
        """}
        client.save(files)

        client.run("install conanfile.txt %s --build missing" % self.settings)
        info_path = os.path.join(client.current_folder, CONANINFO)
        conan_info = ConanInfo.load_file(info_path)
        self.assertEqual("", conan_info.options.dumps())
        self.assertIn("Hello0:language=1", conan_info.full_options.dumps())
        self.assertIn("Hello0/0.1@lasote/stable:8b964e421a5b7e48b7bc19b94782672be126be8b",
                      conan_info.full_requires.dumps())

        files = {CONANFILE_TXT: """[requires]
        Hello0/0.1@lasote/stable

        [options]
        Hello0:language=0
        """}
        client.save(files)
        client.run("install . %s --build missing" % self.settings)

        info_path = os.path.join(client.current_folder, CONANINFO)
        conan_info = ConanInfo.load_file(info_path)
        self.assertEqual("", conan_info.options.dumps())
        # For conan install options are not cached anymore
        self.assertIn("Hello0:language=0", conan_info.full_options.dumps())

        # it is necessary to clean the cached conaninfo
        client.save(files, clean_first=True)
        client.run("install ./conanfile.txt %s --build missing" % self.settings)
        conan_info = ConanInfo.load_file(info_path)
        self.assertEqual("", conan_info.options.dumps())
        self.assertIn("Hello0:language=0", conan_info.full_options.dumps())
        self.assertIn("Hello0/0.1@lasote/stable:2e38bbc2c3ef1425197c8e2ffa8532894c347d26",
                      conan_info.full_requires.dumps())

    def cross_platform_msg_test(self):
        # Explicit with os_build and os_arch settings
        message = "Cross-build from 'Linux:x86_64' to 'Windows:x86_64'"
        self._create("Hello0", "0.1", settings='"os_build", "os", "arch_build", "arch", "compiler"')
        self.client.run("install Hello0/0.1@lasote/stable -s os_build=Linux -s os=Windows",
                        ignore_error=True)
        self.assertIn(message, self.client.user_io.out)

        # Implicit detection when not available (retrocompatibility)
        bad_os = "Linux" if platform.system() != "Linux" else "Macos"
        message = "Cross-build from '%s:x86_64' to '%s:x86_64'" % (detected_os(), bad_os)
        self._create("Hello0", "0.1")
        self.client.run("install Hello0/0.1@lasote/stable -s os=%s" % bad_os, ignore_error=True)
        self.assertIn(message, self.client.user_io.out)

    def install_cwd_test(self):
        conanfile = """from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "0.1"
    settings = "os"
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/stable")
        client.save({"conanfile.txt": "[requires]\nHello/0.1@lasote/stable"}, clean_first=True)

        client.run("install . --build=missing -s os=Windows -s os_build=Windows --install-folder=win_dir")
        self.assertIn("Hello/0.1@lasote/stable from local cache\n",
                      client.out)  # Test "from local cache" output message
        client.run("install . --build=missing -s os=Macos -s os_build=Macos --install-folder=os_dir")
        conaninfo = load(os.path.join(client.current_folder, "win_dir/conaninfo.txt"))
        self.assertIn("os=Windows", conaninfo)
        self.assertNotIn("os=Macos", conaninfo)
        conaninfo = load(os.path.join(client.current_folder, "os_dir/conaninfo.txt"))
        self.assertNotIn("os=Windows", conaninfo)
        self.assertIn("os=Macos", conaninfo)

    def install_reference_not_conanbuildinfo_test(self):
        conanfile = """from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "0.1"
    settings = "os"
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . conan/stable")
        client.save({}, clean_first=True)
        client.run("install Hello/0.1@conan/stable")
        self.assertFalse(os.path.exists(os.path.join(client.current_folder, "conanbuildinfo.txt")))

    def install_with_profile_test(self):
        # Test for https://github.com/conan-io/conan/pull/2043
        conanfile = """from conans import ConanFile
class TestConan(ConanFile):
    settings = "os"
    def requirements(self):
        self.output.info("PKGOS=%s" % self.settings.os)
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("profile new myprofile")
        client.run("profile update settings.os=Linux myprofile")
        client.run("install . -pr=myprofile --build")
        self.assertIn("PKGOS=Linux", client.out)
        mkdir(os.path.join(client.current_folder, "myprofile"))
        client.run("install . -pr=myprofile")
        client.run("profile new myotherprofile")
        client.run("profile update settings.os=FreeBSD myotherprofile")
        client.run("install . -pr=myotherprofile")
        self.assertIn("PKGOS=FreeBSD", client.out)
        client.save({"myotherprofile": "Some garbage without sense [garbage]"})
        client.run("install . -pr=myotherprofile")
        self.assertIn("PKGOS=FreeBSD", client.out)
        error = client.run("install . -pr=./myotherprofile", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Error parsing the profile", client.out)

    def install_with_path_errors_test(self):
        client = TestClient()

        # Install without path param not allowed
        error = client.run("install", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Exiting with code: 2", client.out)

        # Path with wrong conanfile.txt path
        error = client.run("install not_real_dir/conanfile.txt --install-folder subdir",
                           ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Conanfile not found", client.out)

        # Path with wrong conanfile.py path
        error = client.run("install not_real_dir/conanfile.py --install-folder build",
                           ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Conanfile not found", client.out)

    def install_broken_reference_test(self):
        client = TestClient(servers={"default": TestServer()},
                            users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . Hello/0.1@lasote/stable")
        client.run("remote add_ref Hello/0.1@lasote/stable default")
        conan_reference = ConanFileReference.loads("Hello/0.1@lasote/stable")
        rmdir(os.path.join(client.client_cache.conan(conan_reference)))

        error = client.run("install Hello/0.1@lasote/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Hello/0.1@lasote/stable was not found in remote 'default'",
                      client.out)

        # If it was associated, it has to be desasociated
        client.run("remote remove_ref Hello/0.1@lasote/stable")
        error = client.run("install Hello/0.1@lasote/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Unable to find 'Hello/0.1@lasote/stable' in remotes",
                      client.out)
