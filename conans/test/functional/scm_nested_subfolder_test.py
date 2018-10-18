import unittest
from conans.test.utils.tools import TestServer, TestClient, create_local_git_repo
from conans.client.tools.scm import Git


class SCMNestedSubfolderTest(unittest.TestCase):

    # Testing as of issue #3423: https://github.com/conan-io/conan/issues/3423
    def basic_test(self):
        server = TestServer()
        servers = {"default": server}

        # Create a project with git
        files = {'conanfile.py': """from conans import ConanFile
class MyPkg(ConanFile):
    name= "package"
    version = "1.0"

    scm = {
        "type": "git",
        "subfolder": "hello/to/you",
        "url": "auto",
        "revision": "auto"
    }

"""}
        path, _ = create_local_git_repo(files)
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        git = Git(client.current_folder)
        git.clone(path)

        # Upload to 'remote'
        client.run("export . lasote/stable")
        client.run("upload package/1.0@lasote/stable")

        # Consume the project
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        error = client.run("install package/1.0@lasote/stable --build=package")
        self.assertFalse(error)
