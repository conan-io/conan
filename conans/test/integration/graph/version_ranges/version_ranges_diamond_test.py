import textwrap
import unittest
from collections import OrderedDict

from parameterized import parameterized

from conans.paths import CONANFILE
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, \
    inc_package_manifest_timestamp, inc_recipe_manifest_timestamp


class VersionRangesUpdatingTest(unittest.TestCase):

    def test_update_remote(self):
        # https://github.com/conan-io/conan/issues/5333
        client = TestClient(servers={"default": TestServer()},
                            users={"default": [("lasote", "mypass")]})
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Boost(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . boost/1.68.0@lasote/stable")
        client.run("create . boost/1.69.0@lasote/stable")
        client.run("create . boost/1.70.0@lasote/stable")
        client.run("upload * -r=default --all --confirm")
        client.run("remove * -f")
        conanfile = textwrap.dedent("""
            [requires]
            boost/[>=1.68.0]@lasote/stable
            """)
        client.save({"conanfile.txt": conanfile}, clean_first=True)
        client.run("install .")
        self.assertIn("boost/*@lasote/stable versions found in 'default' remote", client.out)
        self.assertIn("resolved to 'boost/1.70.0@lasote/stable' in remote 'default'", client.out)
        self.assertNotIn("boost/1.69.0", client.out)
        self.assertNotIn("boost/1.68.0", client.out)
        client.run("install .")
        self.assertIn("resolved to 'boost/1.70.0@lasote/stable' in local cache", client.out)
        self.assertIn("boost/1.70.0", client.out)
        self.assertNotIn("boost/1.69.0", client.out)
        self.assertNotIn("boost/1.68.0", client.out)

        client.run("install . --update")
        self.assertIn("resolved to 'boost/1.70.0@lasote/stable' in remote 'default'", client.out)
        self.assertIn("boost/1.70.0", client.out)
        self.assertNotIn("boost/1.69.0", client.out)
        self.assertNotIn("boost/1.68.0", client.out)

    def test_update(self):
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
        client.run("install .")
        # Resolves to local package
        self.assertIn("Pkg/1.1@lasote/testing: Already installed!", client.out)
        client.run("install . --update")
        # Resolves to remote package
        self.assertIn("Pkg/1.2@lasote/testing: Package installed", client.out)
        self.assertNotIn("Pkg/1.1", client.out)

        # removes remote
        client.run("remove Pkg* -r=default --f")
        # Resolves to local package
        client.run("install .")
        self.assertIn("Pkg/1.2@lasote/testing: Already installed!", client.out)
        # Update also resolves to local package
        client.run("install . --update")
        self.assertIn("Pkg/1.2@lasote/testing: Already installed!", client.out)
        self.assertNotIn("Pkg/1.1", client.out)

    def test_update_pkg(self):
        server = TestServer()
        client = TestClient(servers={"default": server},
                            users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class HelloReuseConan(ConanFile):
    def package_info(self):
        self.output.info("PACKAGE_INFO {}")
"""
        client.save({"conanfile.py": conanfile.format("1.1")})
        client.run("create . Pkg/1.1@lasote/testing")
        client.save({"conanfile.py": conanfile.format("1.2")})
        client.run("create . Pkg/1.2@lasote/testing")
        client.run("upload Pkg* -r=default --all --confirm")
        consumer = """from conans import ConanFile
class HelloReuseConan(ConanFile):
    requires = "Pkg/[~1]@lasote/testing"
"""
        client.save({"conanfile.py": consumer})
        client.run("install .")
        # Resolves to local package
        self.assertIn("Pkg/1.2@lasote/testing: Already installed!", client.out)
        self.assertIn("Pkg/1.2@lasote/testing: PACKAGE_INFO 1.2", client.out)

        # modify remote 1.2
        client2 = TestClient(servers={"default": server},
                             users={"default": [("lasote", "mypass")]})
        client2.save({"conanfile.py": conanfile.format("*1.2*")})
        client2.run("create . Pkg/1.2@lasote/testing")

        # Make sure timestamp increases, in some machines in testing,
        # it can fail due to same timestamp
        inc_recipe_manifest_timestamp(client2.cache, "Pkg/1.2@lasote/testing", 1)
        inc_package_manifest_timestamp(client2.cache,
                                       "Pkg/1.2@lasote/testing:%s" % NO_SETTINGS_PACKAGE_ID,
                                       1)

        client2.run("upload Pkg* -r=default --all --confirm")

        client.run("install .")
        # Resolves to local package
        self.assertIn("Pkg/1.2@lasote/testing: Already installed!", client.out)
        self.assertIn("Pkg/1.2@lasote/testing: PACKAGE_INFO 1.2", client.out)

        client.run("install . --update")
        # Resolves to remote new recipe and package
        self.assertIn("Pkg/1.2@lasote/testing: Package installed", client.out)
        self.assertNotIn("Pkg/1.2@lasote/testing: PACKAGE_INFO 1.2", client.out)
        self.assertIn("Pkg/1.2@lasote/testing: PACKAGE_INFO *1.2*", client.out)


class VersionRangesMultiRemoteTest(unittest.TestCase):

    def setUp(self):
        self.servers = OrderedDict()
        self.servers["default"] = TestServer()
        self.servers["other"] = TestServer()
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")],
                                                              "other": [("lasote", "mypass")]})

    def _export(self, name, version, deps=None, export=True, upload=True, remote="default"):
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
                self.client.run("upload %s/%s@lasote/stable -r=%s" % (name, version, remote))

    def test_resolve_from_remotes(self):
        self._export("Hello0", "0.1")
        self._export("Hello0", "0.2")
        self._export("Hello0", "0.3", remote="other")
        self._export("Hello1", "0.1", ["Hello0/[>0.1,<0.4]@lasote/stable"], export=False,
                     upload=False)

        for remote, solution in [("default", "0.2"), ("other", "0.3")]:
            self.client.run('remove "Hello0/0.*" -f')
            self.client.run("install . --build missing -r=%s" % remote)
            self.assertIn("Version range '>0.1,<0.4' required by "
                          "'conanfile.py (Hello1/0.1)' "
                          "resolved to 'Hello0/%s@lasote/stable'" % solution,
                          self.client.out)
            self.assertIn("conanfile.py (Hello1/0.1): Generated conaninfo.txt",
                          self.client.out)
            content = self.client.load("conaninfo.txt")
            self.assertIn("Hello0/%s@lasote/stable" % solution, content)


class VersionRangesDiamondTest(unittest.TestCase):

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

    def test_local_then_remote(self):
        self._export("Hello0", "0.1")
        self._export("Hello0", "0.2")
        self._export("Hello0", "0.3")
        self._export("Hello0", "1.4")
        self._export("Hello1", "0.1", ["Hello0/[>0.1,<0.3]@lasote/stable"], export=False,
                     upload=False)

        self.client.run('remove "Hello0/0.*" -f')
        self.client.run("install . --build missing")
        self.assertIn("Version range '>0.1,<0.3' required by 'conanfile.py (Hello1/0.1)' "
                      "resolved to 'Hello0/0.2@lasote/stable'", self.client.out)
        self.assertIn("conanfile.py (Hello1/0.1): Generated conaninfo.txt",
                      self.client.out)

        content = self.client.load("conaninfo.txt")
        self.assertIn("Hello0/0.2@lasote/stable", content)

    @parameterized.expand([(False, ), (True,)])
    def test_reuse(self, upload):
        self._export("Hello0", "0.1", upload=upload)
        self._export("Hello0", "0.2", upload=upload)
        self._export("Hello0", "0.3", upload=upload)
        self._export("Hello1", "0.1", ["Hello0/[>0.1,<0.3]@lasote/stable"], upload=upload)
        self._export("Hello2", "0.1", ["Hello0/[0.2]@lasote/stable"], upload=upload)
        self._export("Hello3", "0.1", ["Hello1/[>=0]@lasote/stable", "Hello2/[~=0]@lasote/stable"],
                     export=False, upload=upload)

        if upload:
            self.client.run('remove "*" -f')

        self.client.run("install . --build missing")

        def check1():
            self.assertIn("Version range '~=0' required by 'conanfile.py (Hello3/0.1)' "
                          "resolved to 'Hello2/0.1@lasote/stable'", self.client.out)
            self.assertIn("Version range '>0.1,<0.3' required by 'Hello1/0.1@lasote/stable' "
                          "resolved to 'Hello0/0.2@lasote/stable'", self.client.out)
            self.assertIn("Version range '0.2' required by 'Hello2/0.1@lasote/stable' resolved "
                          "to 'Hello0/0.2@lasote/stable'", self.client.out)
            self.assertNotIn("Conflict", self.client.out)
            self.assertIn("conanfile.py (Hello3/0.1): Generated conaninfo.txt",
                          self.client.out)

            content = self.client.load("conaninfo.txt")
            self.assertIn("Hello0/0.2@lasote/stable", content)
            self.assertIn("Hello1/0.1@lasote/stable", content)
            self.assertIn("Hello2/0.1@lasote/stable", content)

        check1()

        if upload:
            self._export("Hello0", "0.2.1", upload=upload)
            self.client.run('remove Hello0/0.2.1@lasote/stable -f')
            self._export("Hello3", "0.1", ["Hello1/[>=0]@lasote/stable",
                                           "Hello2/[~=0]@lasote/stable"],
                         export=False, upload=upload)
            self.client.run("install . --build missing")
            check1()
            # Now update
            self.client.run("install . --update --build missing")
            self.assertIn("Version range '~=0' required by 'conanfile.py (Hello3/0.1)' "
                          "resolved to 'Hello2/0.1@lasote/stable'", self.client.out)
            self.assertIn("Version range '>0.1,<0.3' required by 'Hello1/0.1@lasote/stable' "
                          "resolved to 'Hello0/0.2.1@lasote/stable'", self.client.out)
            self.assertIn("Version range '0.2' required by 'Hello2/0.1@lasote/stable' resolved "
                          "to 'Hello0/0.2.1@lasote/stable'", self.client.out)
            self.assertNotIn("Conflict", self.client.out)
            self.assertIn("conanfile.py (Hello3/0.1): Generated conaninfo.txt",
                          self.client.out)

            content = self.client.load("conaninfo.txt")
            self.assertIn("Hello0/0.2.1@lasote/stable", content)
            self.assertIn("Hello1/0.1@lasote/stable", content)
            self.assertIn("Hello2/0.1@lasote/stable", content)

    def test_no_joint_compatibility_resolved(self):
        """Test to verify that conan is not resolving using joint-compatibility of the full graph
        and you need to specify the right order or override downstream the conflict"""
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

        self.assertIn("Conflict in RequirementOne/1.2.3@lasote/stable:\n"
            "    'RequirementOne/1.2.3@lasote/stable' requires "
            "'ProblemRequirement/1.0.0@lasote/stable' while 'RequirementTwo/4.5.6@lasote/stable'"
            " requires 'ProblemRequirement/1.1.0@lasote/stable'.\n"
            "    To fix this conflict you need to override the package 'ProblemRequirement' in "
            "your root package.", self.client.out)

        # Change the order, now it resolves correctly
        self._export("Project", "1.0.0",
                     ["RequirementOne/[=1.2.3]@lasote/stable",
                      "RequirementTwo/[=4.5.6]@lasote/stable",
                      ], upload=True)
        self.client.run("remove '*' -f")
        self.client.run("install Project/1.0.0@lasote/stable --build missing")
