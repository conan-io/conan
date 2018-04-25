import unittest

from conans import tools
from conans.test.utils.tools import TestClient
from conans.model.ref import ConanFileReference
from conans.util.files import load
import os
from conans.test.utils.test_files import temp_folder
from parameterized import parameterized


class GitHelpersTest(unittest.TestCase):

    @parameterized.expand([("", "source"), ("auto", "branch"), ("some_url", "commit")])
    def copy_local_source_test(self, url, checkout):
        client = TestClient()
        conanfile = self._conanfile(url, checkout)
        client.save({"conanfile.py": conanfile,
                     "src/mysrc.cpp": "mysource!!"})

        client.run("create . Pkg/0.1@user/testing")
        ref = ConanFileReference.loads("Pkg/0.1@user/testing")
        contents = load(os.path.join(client.client_cache.export(ref), "conanfile.py"))
        self.assertIn('"checkout": "source"', contents)
        self.assertIn("WARN: SCM not fetching sources. Copying sources from", client.out)
        self.assertIn("SOURCE!: mysource!!", client.out)

    def local_flow_test(self):
        client = TestClient()
        conanfile = self._conanfile("", "source")
        client.save({"conanfile.py": conanfile,
                     "src/mysrc.cpp": "mysource!!"})

        client.run("source .")
        self.assertNotIn("SCM", client.out)
        self.assertIn("SOURCE!: mysource!!", client.out)

    def use_remote_test(self):
        client = TestClient()
        conanfile = self._conanfile("auto", "commit")

        tmp_folder = temp_folder().replace("\\", "/")
        self._commit(client, conanfile, tmp_folder)

        with tools.chdir(client.current_folder):
            client.runner('git clone "%s" .' % tmp_folder)

        client.run("export . Pkg/0.1@user/testing")

        ref = ConanFileReference.loads("Pkg/0.1@user/testing")
        cache_conanfilepath = os.path.join(client.client_cache.export(ref), "conanfile.py")
        contents = load(cache_conanfilepath)
        self.assertNotIn('"checkout": "source"', contents)

        client.run("create . Pkg/0.1@user/testing")
        self.assertNotIn("SCM not fetching sources", client.out)
        self.assertIn("Cloning into", client.out)
        self.assertIn("SOURCE!: mysource!!", client.out)

        # Do local modification
        client.save({"src/mysrc.cpp": "mysource2!!"})
        client.run("create . Pkg/0.1@user/testing")
        contents = load(cache_conanfilepath)
        self.assertIn('"checkout": "source"', contents)

        self.assertIn("SCM not fetching sources", client.out)
        self.assertNotIn("Cloning into", client.out)
        self.assertIn("SOURCE!: mysource2!!", client.out)

    @staticmethod
    def _conanfile(url, checkout):
        conanfile = """from conans import ConanFile
from conans.tools import load
class Pkg(ConanFile):
    scm = {"url": "%s",
           "checkout": "%s"}

    def source(self):
        self.output.info("SOURCE!: {}".format(load("src/mysrc.cpp")))
"""
        return conanfile % (url.replace("\\", "/"), checkout)

    @staticmethod
    def _commit(client, conanfile, folder):
        client.save({"conanfile.py": conanfile,
                     "src/mysrc.cpp": "mysource!!"}, path=folder)
        with tools.chdir(folder):
            client.runner('git init .')
            client.runner('git add .')
            client.runner('git config user.name myname')
            client.runner('git config user.email myname@mycompany.com')
            client.runner('git commit -m "mymsg"')
