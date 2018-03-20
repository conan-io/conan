import unittest

from conans import tools
from conans.test.utils.tools import TestClient
from conans.model.ref import ConanFileReference
from conans.util.files import load
import os
from conans.test.utils.test_files import temp_folder


class GitHelpersTest(unittest.TestCase):

    def copy_local_source_test(self):
        client = TestClient()
        conanfile = self._conanfile(client.current_folder, "source")

        self._commit(client, conanfile, client.current_folder)

        client.run("create . Pkg/0.1@user/testing")
        self.assertNotIn("Cloning into", client.out)
        self.assertIn("Checkout not defined. Copying sources", client.out)
        self.assertIn("SOURCE!: mysource!!", client.out)

    def clone_local_source_test(self):
        client = TestClient()
        conanfile = self._conanfile(client.current_folder, "master")
        self._commit(client, conanfile, client.current_folder)

        client.run("create . Pkg/0.1@user/testing")
        self.assertNotIn("Checkout not defined. Copying sources", client.out)
        self.assertIn("Cloning into", client.out)
        self.assertIn("SOURCE!: mysource!!", client.out)

    def use_branch_test(self):
        client = TestClient()
        conanfile = self._conanfile("auto", "branch")

        self._commit(client, conanfile, client.current_folder)

        client.run("export . Pkg/0.1@user/testing")
        ref = ConanFileReference.loads("Pkg/0.1@user/testing")
        contents = load(os.path.join(client.client_cache.export(ref), "conanfile.py"))

        self.assertIn('cvs_checkout = "master"', contents)

        client.run("create . Pkg/0.1@user/testing")
        self.assertNotIn("Checkout not defined. Copying sources", client.out)
        self.assertIn("Cloning into", client.out)
        self.assertIn("SOURCE!: mysource!!", client.out)

    def use_commit_test(self):
        client = TestClient()
        conanfile = self._conanfile("auto", "commit")

        self._commit(client, conanfile, client.current_folder)

        client.run("export . Pkg/0.1@user/testing")
        ref = ConanFileReference.loads("Pkg/0.1@user/testing")
        contents = load(os.path.join(client.client_cache.export(ref), "conanfile.py"))

        self.assertNotIn('cvs_checkout = "commit"', contents)

        client.run("create . Pkg/0.1@user/testing")
        self.assertNotIn("Checkout not defined. Copying sources", client.out)
        self.assertIn("Cloning into", client.out)
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
        self.assertNotIn('cvs_checkout = "commit"', contents)

        client.run("create . Pkg/0.1@user/testing")
        self.assertNotIn("Checkout not defined. Copying sources", client.out)
        self.assertIn("Cloning into", client.out)
        self.assertIn("SOURCE!: mysource!!", client.out)

        # Do local modification
        client.save({"src/mysrc.cpp": "mysource2!!"})
        client.run("create . Pkg/0.1@user/testing")
        contents = load(cache_conanfilepath)
        self.assertIn('cvs_checkout = "source"', contents)

        self.assertIn("Checkout not defined. Copying sources", client.out)
        self.assertNotIn("Cloning into", client.out)
        self.assertIn("SOURCE!: mysource2!!", client.out)

    @staticmethod
    def _conanfile(url, checkout):
        conanfile = """from conans import ConanFile
from conans.tools import load
class Pkg(ConanFile):
    cvs_url = "%s"
    cvs_checkout = "%s"

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


