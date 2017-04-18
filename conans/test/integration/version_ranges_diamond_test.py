import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.paths import CONANFILE
from conans.util.files import load
import os
from nose_parameterized import parameterized


class VersionRangesMultiRemoteTest(unittest.TestCase):

    def setUp(self):
        self.servers = {"default": TestServer(),
                        "other": TestServer()}
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
            self.client.run("export lasote/stable")
            if upload:
                self.client.run("upload %s/%s@lasote/stable -r=%s" % (name, version, remote))

    def resolve_from_remotes_test(self):
        self._export("Hello0", "0.1")
        self._export("Hello0", "0.2")
        self._export("Hello0", "0.3", remote="other")
        self._export("Hello1", "0.1", ["Hello0/[>0.1,<0.4]@lasote/stable"], export=False,
                     upload=False)

        for remote, solution in [("default", "0.2"), ("other", "0.3")]:
            self.client.run('remove "Hello0/0.*" -f')
            self.client.run("install . --build missing -r=%s" % remote)
            self.assertIn("Version range '>0.1,<0.4' required by 'None' "
                          "resolved to 'Hello0/%s@lasote/stable'" % solution,
                          self.client.user_io.out)
            self.assertIn("PROJECT: Generated conaninfo.txt", self.client.user_io.out)
            content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
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
            self.client.run("export lasote/stable")
            if upload:
                self.client.run("upload %s/%s@lasote/stable" % (name, version))

    def local_then_remote_test(self):
        self._export("Hello0", "0.1")
        self._export("Hello0", "0.2")
        self._export("Hello0", "0.3")
        self._export("Hello0", "1.4")
        self._export("Hello1", "0.1", ["Hello0/[>0.1,<0.3]@lasote/stable"], export=False,
                     upload=False)

        self.client.run('remove "Hello0/0.*" -f')
        self.client.run("install . --build missing")
        self.assertIn("Version range '>0.1,<0.3' required by 'None' "
                      "resolved to 'Hello0/0.2@lasote/stable'", self.client.user_io.out)
        self.assertIn("PROJECT: Generated conaninfo.txt", self.client.user_io.out)

        content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("Hello0/0.2@lasote/stable", content)

    @parameterized.expand([(False, ), (True,)
                           ])
    def reuse_test(self, upload):
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
            self.assertIn("Version range '~=0' required by 'None' resolved to "
                          "'Hello2/0.1@lasote/stable'", self.client.user_io.out)
            self.assertIn("Version range '>0.1,<0.3' required by 'Hello1/0.1@lasote/stable' "
                          "resolved to 'Hello0/0.2@lasote/stable'", self.client.user_io.out)
            self.assertIn("Version range '0.2' required by 'Hello2/0.1@lasote/stable' resolved "
                          "to 'Hello0/0.2@lasote/stable'", self.client.user_io.out)
            self.assertNotIn("Conflict", self.client.user_io.out)
            self.assertIn("PROJECT: Generated conaninfo.txt", self.client.user_io.out)

            content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
            self.assertIn("Hello0/0.2@lasote/stable", content)
            self.assertIn("Hello1/0.1@lasote/stable", content)
            self.assertIn("Hello2/0.1@lasote/stable", content)

        check1()

        if upload:
            self._export("Hello0", "0.2.1", upload=upload)
            self.client.run('remove Hello0/0.2.1@lasote/stable -f')
            self._export("Hello3", "0.1", ["Hello1/[>=0]@lasote/stable", "Hello2/[~=0]@lasote/stable"],
                         export=False, upload=upload)
            self.client.run("install . --build missing")
            check1()
            # Now update
            self.client.run("install . --update --build missing")
            self.assertIn("Version range '~=0' required by 'None' resolved to "
                          "'Hello2/0.1@lasote/stable'", self.client.user_io.out)
            self.assertIn("Version range '>0.1,<0.3' required by 'Hello1/0.1@lasote/stable' "
                          "resolved to 'Hello0/0.2.1@lasote/stable'", self.client.user_io.out)
            self.assertIn("Version range '0.2' required by 'Hello2/0.1@lasote/stable' resolved "
                          "to 'Hello0/0.2.1@lasote/stable'", self.client.user_io.out)
            self.assertNotIn("Conflict", self.client.user_io.out)
            self.assertIn("PROJECT: Generated conaninfo.txt", self.client.user_io.out)

            content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
            self.assertIn("Hello0/0.2.1@lasote/stable", content)
            self.assertIn("Hello1/0.1@lasote/stable", content)
            self.assertIn("Hello2/0.1@lasote/stable", content)
