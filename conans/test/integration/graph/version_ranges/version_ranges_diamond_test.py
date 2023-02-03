import textwrap
import unittest
from collections import OrderedDict

import pytest
from parameterized import parameterized

from conans.paths import CONANFILE
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, \
    inc_package_manifest_timestamp, inc_recipe_manifest_timestamp


@pytest.mark.xfail(reason="Version ranges have changed")
class VersionRangesUpdatingTest(unittest.TestCase):

    def test_update_remote(self):
        # https://github.com/conan-io/conan/issues/5333
        client = TestClient(servers={"default": TestServer()}, inputs=["admin", "password"])
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Boost(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=boost --version=1.68.0 --user=lasote --channel=stable")
        client.run("create . --name=boost --version=1.69.0 --user=lasote --channel=stable")
        client.run("create . --name=boost --version=1.70.0 --user=lasote --channel=stable")
        client.run("upload * -r=default --confirm")
        client.run("remove * -c")
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
        client = TestClient(servers={"default": TestServer()}, inputs=["admin", "password"])

        client.save({"pkg.py": GenConanfile()})
        client.run("create pkg.py --name=pkg --veersion=1.1 --user=lasote --channel=testing")
        client.run("create pkg.py --name=pkg --veersion=1.2 --user=lasote --channel=testing")
        client.run("upload pkg* -r=default --confirm")
        client.run("remove pkg/1.2@lasote/testing -c")

        client.save({"consumer.py": GenConanfile().with_requirement("pkg/[~1]@lasote/testing")})
        client.run("install consumer.py")
        # Resolves to local package
        self.assertIn("pkg/1.1@lasote/testing: Already installed!", client.out)
        client.run("install consumer.py --update")
        # Resolves to remote package
        self.assertIn("pkg/1.2@lasote/testing: Package installed", client.out)
        self.assertNotIn("pkg/1.1", client.out)

        # newer in cache that in remotes and updating, should resolve the cache one
        client.run("create pkg.py --name=pkg --veersion=1.3 --user=lasote --channel=testing")
        client.run("install consumer.py --update")
        self.assertIn("pkg/1.3@lasote/testing: Already installed!", client.out)
        client.run("remove pkg/1.3@lasote/testing -c")

        # removes remote
        client.run("remove Pkg* -r=default --c")
        # Resolves to local package
        client.run("install consumer.py")
        self.assertIn("pkg/1.2@lasote/testing: Already installed!", client.out)
        # Update also resolves to local package
        client.run("install consumer.py --update")
        self.assertIn("pkg/1.2@lasote/testing: Already installed!", client.out)
        self.assertNotIn("pkg/1.1", client.out)

    @pytest.mark.xfail(reason="cache2.0 revisit test")
    def test_update_pkg(self):
        server = TestServer()
        client = TestClient(servers={"default": server}, inputs=["admin", "password"])
        conanfile = """from conan import ConanFile
class HelloReuseConan(ConanFile):
    def package_info(self):
        self.output.info("PACKAGE_INFO {}")
"""
        client.save({"conanfile.py": conanfile.format("1.1")})
        client.run("create . --name=pkg --version=1.1 --user=lasote --channel=testing")
        client.save({"conanfile.py": conanfile.format("1.2")})
        client.run("create . --name=pkg --version=1.2 --user=lasote --channel=testing")
        client.run("upload pkg* -r=default --confirm")
        consumer = """from conan import ConanFile
class HelloReuseConan(ConanFile):
    requires = "pkg/[~1]@lasote/testing"
"""
        client.save({"conanfile.py": consumer})
        client.run("install .")
        # Resolves to local package
        self.assertIn("pkg/1.2@lasote/testing: Already installed!", client.out)
        self.assertIn("pkg/1.2@lasote/testing: PACKAGE_INFO 1.2", client.out)

        # modify remote 1.2
        client2 = TestClient(servers={"default": server}, inputs=["admin", "password"])
        client2.save({"conanfile.py": conanfile.format("*1.2*")})
        client2.run("create . --name=pkg --version=1.2 --user=lasote --channel=testing")

        # Make sure timestamp increases, in some machines in testing,
        # it can fail due to same timestamp
        inc_recipe_manifest_timestamp(client2.cache, "pkg/1.2@lasote/testing", 1)
        inc_package_manifest_timestamp(client2.cache,
                                       "pkg/1.2@lasote/testing:%s" % NO_SETTINGS_PACKAGE_ID,
                                       1)

        client2.run("upload pkg* -r=default --confirm")

        client.run("install .")
        # Resolves to local package
        self.assertIn("pkg/1.2@lasote/testing: Already installed!", client.out)
        self.assertIn("pkg/1.2@lasote/testing: PACKAGE_INFO 1.2", client.out)

        client.run("install . --update")
        # Resolves to remote new recipe and package
        self.assertIn("pkg/1.2@lasote/testing: Package installed", client.out)
        self.assertNotIn("pkg/1.2@lasote/testing: PACKAGE_INFO 1.2", client.out)
        self.assertIn("pkg/1.2@lasote/testing: PACKAGE_INFO *1.2*", client.out)


@pytest.mark.xfail(reason="Overrides Output have changed")
class VersionRangesMultiRemoteTest(unittest.TestCase):

    def setUp(self):
        self.servers = OrderedDict()
        self.servers["default"] = TestServer()
        self.servers["other"] = TestServer()
        self.client = TestClient(servers=self.servers, inputs=2*["admin", "password"])

    def _export(self, name, version, deps=None, export=True, upload=True, remote="default"):
        deps = ", ".join(['"%s"' % d for d in deps or []]) or '""'
        conanfile = """
from conan import ConanFile, CMake
import os

class HelloReuseConan(ConanFile):
    name = "%s"
    version = "%s"
    requires = %s
""" % (name, version, deps)
        files = {CONANFILE: conanfile}
        self.client.save(files, clean_first=True)
        if export:
            self.client.run("export . --user=lasote --channel=stable")
            if upload:
                self.client.run("upload %s/%s@lasote/stable -r=%s --only-recipe" % (name, version,
                                                                                    remote))

    def test_resolve_from_remotes(self):
        self._export("hello0", "0.1")
        self._export("hello0", "0.2")
        self._export("hello0", "0.3", remote="other")
        self._export("hello1", "0.1", ["hello0/[>0.1,<0.4]@lasote/stable"], export=False,
                     upload=False)

        for remote, solution in [("default", "0.2"), ("other", "0.3")]:
            self.client.run('remove "hello0/0.*" -c')
            self.client.run("install . --build missing -r=%s" % remote)
            self.assertIn("Version range '>0.1,<0.4' required by "
                          "'conanfile.py (hello1/0.1)' "
                          "resolved to 'hello0/%s@lasote/stable'" % solution,
                          self.client.out)


@pytest.mark.xfail(reason="Overrides Output have changed")
class VersionRangesDiamondTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, inputs=["admin", "password"])

    def _export(self, name, version, deps=None, export=True, upload=True):
        deps = ", ".join(['"%s"' % d for d in deps or []]) or '""'
        conanfile = """
from conan import ConanFile, CMake
import os

class HelloReuseConan(ConanFile):
    name = "%s"
    version = "%s"
    requires = %s
""" % (name, version, deps)
        files = {CONANFILE: conanfile}
        self.client.save(files, clean_first=True)
        if export:
            self.client.run("export . --user=lasote --channel=stable")
            if upload:
                self.client.run("upload %s/%s@lasote/stable -r default --only-recipe" % (name,
                                                                                         version))

    def test_local_then_remote(self):
        self._export("hello0", "0.1")
        self._export("hello0", "0.2")
        self._export("hello0", "0.3")
        self._export("hello0", "1.4")
        self._export("hello1", "0.1", ["hello0/[>0.1,<0.3]@lasote/stable"], export=False,
                     upload=False)

        self.client.run('remove "hello0/0.*" -c')
        self.client.run("install . --build missing")
        self.assertIn("Version range '>0.1,<0.3' required by 'conanfile.py (hello1/0.1)' "
                      "resolved to 'hello0/0.2@lasote/stable'", self.client.out)

    @parameterized.expand([(False, ), (True,)])
    def test_reuse(self, upload):
        self._export("hello0", "0.1", upload=upload)
        self._export("hello0", "0.2", upload=upload)
        self._export("hello0", "0.3", upload=upload)
        self._export("hello1", "0.1", ["hello0/[>0.1,<0.3]@lasote/stable"], upload=upload)
        self._export("Hello2", "0.1", ["hello0/[0.2]@lasote/stable"], upload=upload)
        self._export("Hello3", "0.1", ["hello1/[>=0]@lasote/stable", "hello2/[~=0]@lasote/stable"],
                     export=False, upload=upload)

        if upload:
            self.client.run('remove "*" -c')

        self.client.run("install . --build missing")

        def check1():
            self.assertIn("Version range '~=0' required by 'conanfile.py (Hello3/0.1)' "
                          "resolved to 'hello2/0.1@lasote/stable'", self.client.out)
            self.assertIn("Version range '>0.1,<0.3' required by 'hello1/0.1@lasote/stable' "
                          "resolved to 'hello0/0.2@lasote/stable'", self.client.out)
            self.assertIn("Version range '0.2' required by 'hello2/0.1@lasote/stable' resolved "
                          "to 'hello0/0.2@lasote/stable'", self.client.out)
            self.assertNotIn("Conflict", self.client.out)

        check1()

        if upload:
            self._export("hello0", "0.2.1", upload=upload)
            self.client.run('remove hello0/0.2.1@lasote/stable -c')
            self._export("Hello3", "0.1", ["hello1/[>=0]@lasote/stable",
                                           "hello2/[~=0]@lasote/stable"],
                         export=False, upload=upload)
            self.client.run("install . --build missing")
            check1()
            # Now update
            self.client.run("install . --update --build missing")
            self.assertIn("Version range '~=0' required by 'conanfile.py (Hello3/0.1)' "
                          "resolved to 'hello2/0.1@lasote/stable'", self.client.out)
            self.assertIn("Version range '>0.1,<0.3' required by 'hello1/0.1@lasote/stable' "
                          "resolved to 'hello0/0.2.1@lasote/stable'", self.client.out)
            self.assertIn("Version range '0.2' required by 'hello2/0.1@lasote/stable' resolved "
                          "to 'hello0/0.2.1@lasote/stable'", self.client.out)
            self.assertNotIn("Conflict", self.client.out)

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

        self.client.run("remove '*' -c")
        self.client.run("install --requires=Project/1.0.0@lasote/stable --build missing", assert_error=True)
        self.assertIn("Conflict in RequirementOne/1.2.3@lasote/stable:\n"
            "    'RequirementOne/1.2.3@lasote/stable' requires "
            "'ProblemRequirement/1.0.0@lasote/stable' while 'RequirementTwo/4.5.6@lasote/stable'"
            " requires 'ProblemRequirement/1.1.0@lasote/stable'.\n"
            "    To fix this conflict you need to override the package 'ProblemRequirement' in "
            "your root package.", self.client.out)

        # Change the order, still conflicts, message in different order, but same conflict
        self._export("Project", "1.0.0",
                     ["RequirementOne/[=1.2.3]@lasote/stable",
                      "RequirementTwo/[=4.5.6]@lasote/stable",
                      ], upload=True)
        self.client.run("remove '*' -c")
        self.client.run("install --requires=Project/1.0.0@lasote/stable --build missing", assert_error=True)
        self.assertIn("Conflict in RequirementTwo/4.5.6@lasote/stable:\n"
              "    'RequirementTwo/4.5.6@lasote/stable' requires "
              "'ProblemRequirement/1.1.0@lasote/stable' while 'RequirementOne/1.2.3@lasote/stable'"
              " requires 'ProblemRequirement/1.0.0@lasote/stable'.\n"
              "    To fix this conflict you need to override the package 'ProblemRequirement' in "
              "your root package.", self.client.out)
