import unittest
from conans.test.tools import TestClient
from conans.util.files import load
import os


class ConanScopeTest(unittest.TestCase):

    def conan_scopes_deps_test(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    def build(self):
        if self.scope.dev:
            self.output.warn("DEP DEV")
        if self.scope.other:
            self.output.warn("DEP OTHER")
        '''
        files = {}
        files["conanfile.py"] = conanfile
        client.save(files)
        client.run("export lasote/stable")
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello2"
    version = "0.1"
    def config(self):
        if self.scope.other:
            self.requires("Hello/0.1@lasote/stable", dev=True)
        '''
        files["conanfile.py"] = conanfile
        client.save(files, clean_first=True)
        error = client.run("install --build")
        self.assertFalse(error)
        self.assertNotIn("Hello/0.1@lasote/stable", client.user_io.out)

        error = client.run("install -sc=other=True --build")
        self.assertFalse(error)
        self.assertIn("Hello/0.1@lasote/stable", client.user_io.out)
        client.run("export lasote/stable")

        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    requires = "Hello2/0.1@lasote/stable"
        '''
        files["conanfile.py"] = conanfile
        client.save(files, clean_first=True)
        error = client.run("install --build")
        self.assertFalse(error)
        #print client.user_io.out

        error = client.run("install -sc=Hello2:other=True --build")
        self.assertFalse(error)
        #print client.user_io.out

    def conan_scopes_test(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    def build(self):
        if self.scope.dev:
            self.output.warn("DEP DEV")
        if self.scope.other:
            self.output.warn("DEP OTHER")
        '''
        files = {}
        files["conanfile.py"] = conanfile
        client.save(files)
        client.run("export lasote/stable")
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    requires = "Hello/0.1@lasote/stable"
    def config(self):
        if self.scope.dev:
            self.output.warn("CONFIG_CONSUMER DEV")
        if self.scope.other:
            self.output.warn("CONFIG_CONSUMER OTHER")
    def build(self):
        if self.scope.dev:
            self.output.warn("BUILD_CONSUMER DEV")
        if self.scope.other:
            self.output.warn("BUILD_CONSUMER OTHER")
        '''
        files["conanfile.py"] = conanfile
        client.save(files, clean_first=True)

        error = client.run("install --build")
        self.assertFalse(error)
        self.assertNotIn("WARN: DEP DEV", client.user_io.out)
        self.assertNotIn("WARN: DEP OTHER", client.user_io.out)
        self.assertIn("WARN: CONFIG_CONSUMER DEV", client.user_io.out)
        self.assertNotIn("WARN: CONFIG_CONSUMER OTHER", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER DEV", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER OTHER", client.user_io.out)

        for command in ("install --build -sc other=True", "install --build"):
            error = client.run(command)
            conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
            self.assertIn("[scope]    dev=True    other=True", "".join(conaninfo.splitlines()))
            self.assertFalse(error)
            self.assertNotIn("WARN: DEP DEV", client.user_io.out)
            self.assertNotIn("WARN: DEP OTHER", client.user_io.out)
            self.assertIn("WARN: CONFIG_CONSUMER DEV", client.user_io.out)
            self.assertIn("WARN: CONFIG_CONSUMER OTHER", client.user_io.out)
            self.assertNotIn("WARN: BUILD_CONSUMER DEV", client.user_io.out)
            self.assertNotIn("WARN: BUILD_CONSUMER OTHER", client.user_io.out)

        for command in ("install --build -sc Hello:dev=True", "install --build"):
            error = client.run(command)
            conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
            self.assertIn("[scope]    dev=True    Hello:dev", "".join(conaninfo.splitlines()))
            self.assertFalse(error)
            self.assertIn("WARN: DEP DEV", client.user_io.out)
            self.assertNotIn("WARN: DEP OTHER", client.user_io.out)
            self.assertIn("WARN: CONFIG_CONSUMER DEV", client.user_io.out)
            self.assertNotIn("WARN: CONFIG_CONSUMER OTHER", client.user_io.out)
            self.assertNotIn("WARN: BUILD_CONSUMER DEV", client.user_io.out)
            self.assertNotIn("WARN: BUILD_CONSUMER OTHER", client.user_io.out)

        for command in ("install --build -sc Hello:dev=True -sc Hello:other=True", "install --build"):
            error = client.run(command)
            conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
            self.assertIn("[scope]    dev=True    Hello:dev=True    Hello:other=True",
                          "".join(conaninfo.splitlines()))
            self.assertFalse(error)
            self.assertIn("WARN: DEP DEV", client.user_io.out)
            self.assertIn("WARN: DEP OTHER", client.user_io.out)
            self.assertIn("WARN: CONFIG_CONSUMER DEV", client.user_io.out)
            self.assertNotIn("WARN: CONFIG_CONSUMER OTHER", client.user_io.out)
            self.assertNotIn("WARN: BUILD_CONSUMER DEV", client.user_io.out)
            self.assertNotIn("WARN: BUILD_CONSUMER OTHER", client.user_io.out)
