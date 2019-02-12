# -*- coding: utf-8 -*-
import os
import unittest
import tempfile
from collections import OrderedDict

from parameterized import parameterized

from conans.paths import CONANFILE
from conans.test import CONAN_TEST_FOLDER
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, \
    inc_package_manifest_timestamp, inc_recipe_manifest_timestamp
from conans.util.files import load


def lockfile():
    return tempfile.mktemp(suffix='_lockfile', dir=CONAN_TEST_FOLDER)


class VersionRangesUpdateDoesntAffectLockingTest(unittest.TestCase):
    def update_test(self):
        client = TestClient(servers={"default": TestServer()},
                            users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class HelloReuseConan(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/1.1@lasote/testing")
        client.run("create . Pkg/1.2@lasote/testing")

        client.run("upload Pkg* -r=default --all --confirm")
        client.run("remove Pkg/1.2@lasote/testing -f")
        conanfile = """from conans import ConanFile
class HelloReuseConan(ConanFile):
    requires = "Pkg/[~1]@lasote/testing"
"""
        client.save({"conanfile.py": conanfile})
        lf = lockfile()
        client.run("install .", lock=True, lockfile=lf)

        # Resolves to locked package
        client.run("install .", lockfile=lf)
        self.assertIn("Pkg/1.1@lasote/testing: Already installed!", client.out)
        # Update also resolves to locked package
        client.run("install . --update", lockfile=lf)
        self.assertIn("Pkg/1.1@lasote/testing: Already installed!", client.out)
        self.assertNotIn("Pkg/1.2", client.out)


        # removes remote
        client.run("remove Pkg* -r=default --f")

        # Resolves to locked package
        client.run("install .", lockfile=lf)
        self.assertIn("Pkg/1.1@lasote/testing: Already installed!", client.out)
        # Update also resolves to locked package
        client.run("install . --update", lockfile=lf)
        self.assertIn("Pkg/1.1@lasote/testing: Already installed!", client.out)
        self.assertNotIn("Pkg/1.2", client.out)


class VersionRangesLockedDiamondTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

    def _export(self, name, version, deps=None, export=True, upload=True):
        deps = ", ".join(['"%s"' % d for d in deps or []]) or '""'
        conanfile = """
from conans import ConanFile, CMake
import os

class HelloReuseConan(ConanFile):
    name = "%s"
    version = "%s"
    requires = %s
""" % (name, version, deps)
        files = {CONANFILE: conanfile}
        self.client.save(files, clean_first=True)
        if export:
            self.client.run("export . lasote/stable")
            if upload:
                self.client.run("upload %s/%s@lasote/stable" % (name, version))

    def local_then_remote_test(self):
        self._export("Hello0", "0.1")
        self._export("Hello0", "0.2")
        self._export("Hello0", "0.3")
        self._export("Hello0", "1.4")
        self._export("Hello1", "0.1", ["Hello0/[>0.1 <0.5]@lasote/stable"], export=False,
                     upload=False)

        self.client.run('remove "Hello0/0.*" -f')
        lf = lockfile()
        self.client.run("install . --build missing", lock=True, lockfile=lf)

        def check():
            self.assertIn("Version range '>0.1 <0.5' required by 'conanfile.py (Hello1/0.1@None/None)' "
                          "resolved to 'Hello0/0.3@lasote/stable'", self.client.user_io.out)
            self.assertNotIn("Version range '>0.1 <0.5' required by 'conanfile.py (Hello1/0.1@None/None)' "
                          "resolved to 'Hello0/0.4@lasote/stable'", self.client.user_io.out)
            self.assertIn("conanfile.py (Hello1/0.1@None/None): Generated conaninfo.txt",
                          self.client.out)

            content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
            self.assertIn("Hello0/0.3@lasote/stable", content)

        check()
        # New version
        self._export("Hello0", "0.4")
        self._export("Hello1", "0.1", ["Hello0/[>0.1 <0.5]@lasote/stable"], export=False,
                     upload=False)
        # Rerun with lockfile
        self.client.run("install . --build missing", lockfile=lf)
        check()

    @parameterized.expand([(False, ), (True,)])
    def reuse_test(self, upload):
        self._export("Hello0", "0.1", upload=upload)
        self._export("Hello0", "0.2", upload=upload)
        self._export("Hello1", "0.1", ["Hello0/[>0.1 <0.5]@lasote/stable"], upload=upload)
        self._export("Hello2", "0.1", ["Hello0/[0.2]@lasote/stable"], upload=upload)
        self._export("Hello3", "0.1", ["Hello1/[>=0]@lasote/stable", "Hello2/[~=0]@lasote/stable"],
                     export=False, upload=upload)

        if upload:
            self.client.run('remove "*" -f')

        lf = lockfile()
        self.client.run("install . --build missing", lock=True, lockfile=lf)

        def check1():
            self.assertIn("Version range '~=0' required by 'conanfile.py (Hello3/0.1@None/None)' "
                          "resolved to 'Hello2/0.1@lasote/stable'", self.client.out)
            self.assertIn("Version range '>0.1 <0.5' required by 'Hello1/0.1@lasote/stable' "
                          "resolved to 'Hello0/0.2@lasote/stable'", self.client.user_io.out)
            self.assertNotIn("Version range '>0.1 <0.5' required by 'Hello1/0.1@lasote/stable' "
                             "resolved to 'Hello0/0.2.1@lasote/stable'", self.client.user_io.out)
            self.assertIn("Version range '0.2' required by 'Hello2/0.1@lasote/stable' resolved "
                          "to 'Hello0/0.2@lasote/stable'", self.client.user_io.out)
            self.assertNotIn("Conflict", self.client.user_io.out)
            self.assertIn("conanfile.py (Hello3/0.1@None/None): Generated conaninfo.txt",
                          self.client.out)

            content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
            self.assertIn("Hello0/0.2@lasote/stable", content)
            self.assertIn("Hello1/0.1@lasote/stable", content)
            self.assertIn("Hello2/0.1@lasote/stable", content)

        check1()
        # New version
        self._export("Hello0", "0.2.1", upload=upload)
        self._export("Hello3", "0.1", ["Hello1/[>=0]@lasote/stable", "Hello2/[~=0]@lasote/stable"],
                     export=False, upload=upload)
        # Rerun with lockfile
        self.client.run("install . --build missing", lockfile=lf)
        check1()

        if upload:
            self._export("Hello0", "0.2.2", upload=upload)
            self.client.run('remove Hello0/0.2.*@lasote/stable -f')
            self._export("Hello3", "0.1", ["Hello1/[>=0]@lasote/stable",
                                           "Hello2/[~=0]@lasote/stable"],
                         export=False, upload=upload)
            self.client.run("install . --build missing")
            check1()
            # Now update
            self.client.run("install . --update --build missing")
            self.assertIn("Version range '~=0' required by 'conanfile.py (Hello3/0.1@None/None)' "
                          "resolved to 'Hello2/0.1@lasote/stable'", self.client.out)
            self.assertIn("Version range '>0.1 <0.5' required by 'Hello1/0.1@lasote/stable' "
                          "resolved to 'Hello0/0.2.2@lasote/stable'", self.client.user_io.out)
            self.assertIn("Version range '0.2' required by 'Hello2/0.1@lasote/stable' resolved "
                          "to 'Hello0/0.2.2@lasote/stable'", self.client.user_io.out)
            self.assertNotIn("Conflict", self.client.user_io.out)
            self.assertIn("conanfile.py (Hello3/0.1@None/None): Generated conaninfo.txt",
                          self.client.out)

            content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
            self.assertIn("Hello0/0.2.2@lasote/stable", content)
            self.assertIn("Hello1/0.1@lasote/stable", content)
            self.assertIn("Hello2/0.1@lasote/stable", content)

            # After update, with lockfile should recreate previous version
            self.client.run("install . --build missing", lockfile=lf)
            check1()

    def no_joint_compatibility_resolved_test(self):
        """Test to verify that conan is not resolving using joint-compatibility of the full graph
        and you need to specify the right order or override downstream the conflict."""
        self._export("ProblemRequirement", "1.0.0", upload=True)
        self._export("ProblemRequirement", "1.1.0", upload=True)
        self._export("RequirementOne", "1.2.3",
                     ["ProblemRequirement/[=1.0.0]@lasote/stable"], upload=True)
        self._export("RequirementTwo", "4.5.6",
                     ["ProblemRequirement/[~1]@lasote/stable"], upload=True)
        self._export("Project", "1.0.0",
                     ["RequirementTwo/[=4.5.6]@lasote/stable",
                      "RequirementOne/[=1.2.3]@lasote/stable"], upload=True)

        self.client.run("remove '*' -f")
        self.client.run("install Project/1.0.0@lasote/stable --build missing", assert_error=True)

        self.assertIn("Requirement ProblemRequirement/1.0.0@lasote/stable conflicts with "
                      "already defined ProblemRequirement/1.1.0@lasote/stable", self.client.out)

        # Change the order, now it resolves correctly, pin that version
        lf = lockfile()
        self._export("Project", "1.0.0",
                     ["RequirementOne/[=1.2.3]@lasote/stable",
                      "RequirementTwo/[=4.5.6]@lasote/stable",
                      ], upload=True)
        self.client.run("remove '*' -f")
        self.client.run("install Project/1.0.0@lasote/stable --build missing", lock=True, lockfile=lf)

        # Revert order, but this time use lockfile, should work correctly
        self._export("Project", "1.0.0",
                     ["RequirementTwo/[=4.5.6]@lasote/stable",
                      "RequirementOne/[=1.2.3]@lasote/stable",
                      ], upload=True)
        self.client.run("remove '*' -f")
        self.client.run("install Project/1.0.0@lasote/stable --build missing", lockfile=lf)

    def incorrect_lockfile_no_sections_test(self):
        self._export("Hello0", "1.0", upload=True)
        self._export("Hello1", "1.0", ["Hello0/[~1]@lasote/stable"], upload=True)
        lf = lockfile()
        with open(lf, 'w') as f:
            f.write("Whatever")
        try:
            self.client.run("install . --build missing", lockfile=lf)
        except Exception as e:
            self.assertIn("File contains no section headers.", str(e))

    def incorrect_lockfile_case_insensitive_test(self):
        self._export("Hello0", "1.0", upload=True)
        self._export("Hello1", "1.0", ["Hello0/[~1]@lasote/stable"], upload=True)
        lf = lockfile()
        with open(lf, 'w') as f:
            f.writelines(["[DEFAULT]", "hello0 = 1.0"])
        self.client.run("install . --build missing", lockfile=lf, assert_error=True)
        self.assertIn("Cannot retrieve reference 'Hello0' version from lock file", self.client.out)

    def lockfile_doesnt_have_package_info_test(self):
        self._export("Hello0", "1.0", upload=True)
        self._export("Hello1", "1.0", ["Hello0/[~1]@lasote/stable"], upload=True)
        lf = lockfile()
        open(lf, 'w').close()
        self.client.run("install . --build missing", lockfile=lf, assert_error=True)
        self.assertIn("Cannot retrieve reference 'Hello0' version from lock file", self.client.out)

    def choose_older_version_which_is_pinned_test(self):
        lf = lockfile()
        self._export("Hello0", "1.0", upload=True)
        self._export("Hello1", "1.0", ["Hello0/[>=1]@lasote/stable"], upload=True)
        self.client.run("install . --build missing", lock=True, lockfile=lf)
        content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("Hello0/1.0@lasote/stable", content)

        self._export("Hello0", "2.0", upload=True)
        self._export("Hello1", "1.0", ["Hello0/[>=1]@lasote/stable"], upload=True)
        self.client.run("install . --build missing", lockfile=lf)
        content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("Hello0/1.0@lasote/stable", content)

    def update_lockfile_with_the_same_packages_test(self):
        lf = lockfile()
        self._export("Hello0", "1.0", upload=True)
        self._export("Hello1", "1.0", ["Hello0/[>=1]@lasote/stable"], upload=True)
        self.client.run("install . --build missing", lock=True, lockfile=lf)
        content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("Hello0/1.0@lasote/stable", content)

        self._export("Hello0", "2.0", upload=True)
        self._export("Hello1", "1.0", ["Hello0/[>=1]@lasote/stable"], upload=True)
        self.client.run("install . --build missing", lockfile=lf)
        content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("Hello0/1.0@lasote/stable", content)

        # Update
        self.client.run("install . --build missing", lock=lf, lockfile=lf)
        content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("Hello0/2.0@lasote/stable", content)
        # Check if got updated
        self.client.run("install . --build missing", lockfile=lf)
        content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("Hello0/2.0@lasote/stable", content)

    def update_lockfile_with_new_packages_test(self):
        lf = lockfile()
        self._export("Hello0", "1.0", upload=True)
        self._export("Hello2", "1.0", ["Hello0/[>=1]@lasote/stable"], upload=True)
        self.client.run("install . --build missing", lock=True, lockfile=lf)
        content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("Hello0/1.0@lasote/stable", content)

        self._export("Hello1", "1.0", upload=True)
        self._export("Hello2", "1.0", ["Hello1/[>=1]@lasote/stable"], upload=True)
        self.client.run("install . --build missing", lock=True, lockfile=lf)
        content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("Hello1/1.0@lasote/stable", content)
        self.assertNotIn("Hello0/1.0@lasote/stable", content)

        self._export("Hello0", "1.1", upload=True)
        self._export("Hello1", "1.1", upload=True)
        self._export("Hello3", "1.0", ["Hello0/[>=1]@lasote/stable", "Hello1/[>=1]@lasote/stable"], upload=True)
        self.client.run("install . --build missing", lockfile=lf)
        content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("Hello0/1.0@lasote/stable", content)
        self.assertNotIn("Hello0/1.1@lasote/stable", content)
        self.assertIn("Hello1/1.0@lasote/stable", content)
        self.assertNotIn("Hello1/1.1@lasote/stable", content)
