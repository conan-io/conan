import unittest
from conans.test.utils.tools import TestServer, TestClient, create_local_git_repo
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.model.ref import ConanFileReference
from conans.client.tools.scm import Git
import os
from conans.util.files import save


class SCMNestedSubfolderTest(unittest.TestCase):

    # Testing as of issue #3423: https://github.com/conan-io/conan/issues/3423
    def basic_test(self):
        server = TestServer()
        servers = {"default": server}

        # Create a project with git
        scm = {
            "type": "git",
            "subfolder": "hello/to/you",
            "url": "auto",
            "revision": "auto"
        }
        files = cpp_hello_conan_files(name='package', version='1.0', scm_dict=scm)
        path, _ = create_local_git_repo(files)
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        git = Git(client.current_folder)
        git.clone(path)

        # Upload to 'remote'
        client.run("export . lasote/stable")
        error = client.run("upload package/1.0@lasote/stable")
        self.assertFalse(error)

        # Consume the project
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        error = client.run("install package/1.0@lasote/stable --build=package")
        self.assertFalse(error)
