import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.paths import CONANFILE
from conans.util.files import load, save
import os
from nose_parameterized import parameterized
from conans.model.ref import ConanFileReference


class VersionRangesUpdatingTest(unittest.TestCase):

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

    def update_pkg_test(self):
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
        conan_reference = ConanFileReference.loads("Pkg/1.2@lasote/testing")
        manifest = client2.client_cache.digestfile_conanfile(conan_reference)
        # Make sure timestamp increases, in some machines in testing, it can fail due to same timestamp
        content = load(manifest).splitlines()
        content[0] = str(int(content[0]) + 1)
        save(manifest, "\n".join(content))
        client2.run("upload Pkg* -r=default --all --confirm")

        client.run("install .")
        # Resolves to local package
        self.assertIn("Pkg/1.2@lasote/testing: Already installed!", client.out)
        self.assertIn("Pkg/1.2@lasote/testing: PACKAGE_INFO 1.2", client.out)

        client.run("install . --update")
        # Resolves to local package
        self.assertIn("Pkg/1.2@lasote/testing: Package installed", client.out)
        self.assertNotIn("Pkg/1.2@lasote/testing: PACKAGE_INFO 1.2", client.out)
        self.assertIn("Pkg/1.2@lasote/testing: PACKAGE_INFO *1.2*", client.out)


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
            self.client.run("export . lasote/stable")
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
            self.client.run("export . lasote/stable")
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
