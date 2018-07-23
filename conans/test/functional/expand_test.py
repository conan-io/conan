import unittest

from conans import tools
from conans.test.utils.tools import TestClient, create_local_git_repo

class ExpandTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def _commit_contents(self):
        self.client.runner("git init .", cwd=self.client.current_folder)
        self.client.runner('git config user.email "you@example.com"', cwd=self.client.current_folder)
        self.client.runner('git config user.name "Your Name"', cwd=self.client.current_folder)
        self.client.runner("git add .", cwd=self.client.current_folder)
        self.client.runner('git commit -m  "commiting"', cwd=self.client.current_folder)

    def test_expand_in_version(self):
        conanfile = '''
import os
from conans import ConanFile, tools, conan_expand

def get_version(variable):
    return tools.get_env(variable, "error")

class ConanLib(ConanFile):
    name = "lib"
    version = conan_expand(get_version("MY_VERSION"))

    def source(self):
        self.output.warn("version = '{}'".format(self.version))
'''
        self.client.save({"conanfile.py": conanfile})
        with tools.environment_append({"MY_VERSION": "123"}):
            self.client.run("export . user/channel")
        self.client.run("install lib/123@user/channel --build")
        self.assertIn("version = '123'", self.client.out)

    def test_expand_in_scm_structure(self):
        conanfile = '''
import os
from conans import ConanFile, tools, conan_expand

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    scm = {
        "type": "git",
        "username": conan_expand(tools.get_env("MY_USERNAME", "error")),
        "password": tools.get_env("MY_PASSWORD", "error"),
        "url": "auto",
        "revision": "auto"
    }

    def source(self):
        self.output.warn("scm['username'] = '{}'".format(self.scm['username']))
        self.output.warn("scm['password'] = '{}'".format(self.scm['password']))
'''
        path, commit = create_local_git_repo({"myfile": "contents", "conanfile.py": conanfile},
                                             branch="my_release")
        self.client.current_folder = path
        self.client.runner('git remote add origin https://myrepo.com.git', cwd=path)
        self._commit_contents()

        self.client.save({"conanfile.py": conanfile})
        with tools.environment_append({"MY_USERNAME": "export user", "MY_PASSWORD": "export password"}):
            self.client.run("export . user/channel")
        with tools.environment_append({"MY_USERNAME": "install user", "MY_PASSWORD": "install password"}):
            self.client.run("install lib/0.1@user/channel --build")
        self.assertIn("scm['username'] = 'export user'", self.client.out)
        self.assertIn("scm['password'] = 'install password'", self.client.out)
