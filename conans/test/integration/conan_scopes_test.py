
import unittest
from conans.test.utils.tools import TestClient
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
        client.run("install --build")

        self.assertNotIn("Hello/0.1@lasote/stable", client.user_io.out)

        client.run("install -sc=other=True --build")

        self.assertIn("Hello/0.1@lasote/stable", client.user_io.out)
        client.run("export lasote/stable")

        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    requires = "Hello2/0.1@lasote/stable"
        '''
        files["conanfile.py"] = conanfile
        client.save(files, clean_first=True)
        client.run("install --build")
        client.run("install -sc=Hello2:other=True --build")

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
        self.output.info(self.scope)
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

        client.run("install --build")

        self.assertNotIn("WARN: DEP DEV", client.user_io.out)
        self.assertNotIn("WARN: DEP OTHER", client.user_io.out)
        self.assertIn("WARN: CONFIG_CONSUMER DEV", client.user_io.out)
        self.assertNotIn("WARN: CONFIG_CONSUMER OTHER", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER DEV", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER OTHER", client.user_io.out)

        client.run("install --build -sc other=True")
        conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
        self.assertIn("[scope]    dev=True    other=True", "".join(conaninfo.splitlines()))
        self.assertIn("dev=True, other=True", client.user_io.out)
        self.assertNotIn("WARN: DEP DEV", client.user_io.out)
        self.assertNotIn("WARN: DEP OTHER", client.user_io.out)
        self.assertIn("WARN: CONFIG_CONSUMER DEV", client.user_io.out)
        self.assertIn("WARN: CONFIG_CONSUMER OTHER", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER DEV", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER OTHER", client.user_io.out)

        client.run("install --build -sc Hello:dev=True")
        conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
        self.assertIn("[scope]    dev=True    Hello:dev=True",
                      "".join(conaninfo.splitlines()))
        self.assertIn("WARN: DEP DEV", client.user_io.out)
        self.assertNotIn("WARN: DEP OTHER", client.user_io.out)
        self.assertIn("WARN: CONFIG_CONSUMER DEV", client.user_io.out)
        self.assertNotIn("WARN: CONFIG_CONSUMER OTHER", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER DEV", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER OTHER", client.user_io.out)

        client.run("install --build -sc Hello:other=True")
        conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
        self.assertIn("[scope]    dev=True    Hello:other=True",
                      "".join(conaninfo.splitlines()))
        self.assertNotIn("WARN: DEP DEV", client.user_io.out)
        self.assertIn("WARN: DEP OTHER", client.user_io.out)
        self.assertIn("WARN: CONFIG_CONSUMER DEV", client.user_io.out)
        self.assertNotIn("WARN: CONFIG_CONSUMER OTHER", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER DEV", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER OTHER", client.user_io.out)

        client.run("install --build -sc Hello:other=False")
        conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
        self.assertIn("[scope]    dev=True    Hello:other=False",
                      "".join(conaninfo.splitlines()))
        self.assertNotIn("WARN: DEP DEV", client.user_io.out)
        self.assertNotIn("WARN: DEP OTHER", client.user_io.out)
        self.assertIn("WARN: CONFIG_CONSUMER DEV", client.user_io.out)
        self.assertNotIn("WARN: CONFIG_CONSUMER OTHER", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER DEV", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER OTHER", client.user_io.out)

        client.run("build")
        conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
        self.assertIn("[scope]    dev=True    Hello:other=False",
                      "".join(conaninfo.splitlines()))
        self.assertNotIn("WARN: DEP DEV", client.user_io.out)
        self.assertNotIn("WARN: DEP OTHER", client.user_io.out)
        self.assertNotIn("WARN: CONFIG_CONSUMER DEV", client.user_io.out)
        self.assertNotIn("WARN: CONFIG_CONSUMER OTHER", client.user_io.out)
        self.assertIn("WARN: BUILD_CONSUMER DEV", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER OTHER", client.user_io.out)

    def conan_scopes_pattern_test(self):
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

        client.run("install --build")

        self.assertNotIn("WARN: DEP DEV", client.user_io.out)
        self.assertNotIn("WARN: DEP OTHER", client.user_io.out)
        self.assertIn("WARN: CONFIG_CONSUMER DEV", client.user_io.out)
        self.assertNotIn("WARN: CONFIG_CONSUMER OTHER", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER DEV", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER OTHER", client.user_io.out)

        client.run("install --build -sc ALL:other=True")
        conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
        self.assertIn("[scope]    dev=True    ALL:other=True",
                      "".join(conaninfo.splitlines()))
        self.assertNotIn("WARN: DEP DEV", client.user_io.out)
        self.assertIn("WARN: DEP OTHER", client.user_io.out)
        self.assertIn("WARN: CONFIG_CONSUMER DEV", client.user_io.out)
        self.assertIn("WARN: CONFIG_CONSUMER OTHER", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER DEV", client.user_io.out)
        self.assertNotIn("WARN: BUILD_CONSUMER OTHER", client.user_io.out)

    def conan_dev_requires_test(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Base"
    version = "0.1"
'''
        files = {}
        files["conanfile.py"] = conanfile
        client.save(files)
        client.run("export lasote/stable")
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    dev_requires = "Base/0.1@lasote/stable"
    name = "Hello"
    version = "0.1"
'''
        files = {}
        files["conanfile.py"] = conanfile
        client.save(files)
        client.run("export lasote/stable")
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    dev_requires = "Hello/0.1@lasote/stable"
        '''
        files["conanfile.py"] = conanfile
        client.save(files, clean_first=True)

        client.run("install --build")
        self.assertIn("Hello/0.1@lasote/stable:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                      client.user_io.out)
        self.assertNotIn("Base/0.1@lasote/stable", client.user_io.out)
        client.run("install --build -sc dev=False")
        self.assertNotIn("Hello/0.1@lasote/stable", client.user_io.out)
        self.assertNotIn("Base/0.1@lasote/stable", client.user_io.out)
        client.run("install --build -sc dev=True -sc Hello:dev=True")
        self.assertIn("Hello/0.1@lasote/stable:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                      client.user_io.out)
        self.assertIn("Base/0.1@lasote/stable", client.user_io.out)
