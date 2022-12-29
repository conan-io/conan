import textwrap
import unittest

import pytest

from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE, CONANFILE_TXT
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer

generator = """
from conans.model import Generator
from conans.paths import BUILD_INFO
from conans import ConanFile

class MyCustom_Generator(Generator):
    @property
    def filename(self):
        return "customfile.gen"

    @property
    def content(self):
        return "My custom generator content"


class MyCustomGeneratorPackage(ConanFile):
    name = "MyCustomGen"
    version = "0.2"
"""

consumer = """
[requires]
Hello0/0.1@lasote/stable
MyCustomGen/0.2@lasote/stable

[generators]
MyCustom_Generator
"""

generator_multi = """
from conans.model import Generator
from conans.paths import BUILD_INFO
from conans import ConanFile

class MyCustomMultiGenerator(Generator):
    @property
    def filename(self):
        return "customfile.gen"

    @property
    def content(self):
        return {"file1.gen": "CustomContent1",
                "file2.gen": "CustomContent2"}


class NoMatterTheName(ConanFile):
    name = "MyCustomGen"
    version = "0.2"
"""

consumer_multi = """
[requires]
MyCustomGen/0.2@lasote/stable

[generators]
MyCustomMultiGenerator
"""


class CustomGeneratorTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}

    def test_reuse(self):
        ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")

        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        client.save({"conanfile.py": GenConanfile("Hello0", "0.1")})
        client.run("export . lasote/stable")
        client.run("upload %s" % str(ref))

        gen_ref = ConanFileReference.loads("MyCustomGen/0.2@lasote/stable")
        files = {CONANFILE: generator}
        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        client.save(files)
        client.run("export . lasote/stable")
        client.run("upload %s" % str(gen_ref))

        # Test local, no retrieval
        files = {CONANFILE_TXT: consumer}
        client.save(files, clean_first=True)
        client.run("install . --build")
        generated = client.load("customfile.gen")
        self.assertEqual(generated, "My custom generator content")

        # Test retrieval from remote
        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        files = {CONANFILE_TXT: consumer}
        client.save(files)
        client.run("install . --build")

        generated = client.load("customfile.gen")
        self.assertEqual(generated, "My custom generator content")

    def test_multifile(self):
        gen_ref = ConanFileReference.loads("MyCustomGen/0.2@lasote/stable")
        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        files = {CONANFILE: generator_multi}
        client.save(files)
        client.run("export . lasote/stable")
        client.run("upload %s" % str(gen_ref))

        # Test local, no retrieval
        files = {CONANFILE_TXT: consumer_multi}
        client.save(files, clean_first=True)
        client.run("install . --build")
        self.assertIn("Generator MyCustomMultiGenerator is multifile. "
                      "Property 'filename' not used",
                      client.out)
        for i in (1, 2):
            generated = client.load("file%d.gen" % i)
            self.assertEqual(generated, "CustomContent%d" % i)

    def test_export_template_generator(self):
        templated_generator = """
import os
from conans import ConanFile, load
from conans.model import Generator
class MyCustomTemplateGenerator(Generator):
    @property
    def filename(self):
        return "customfile.gen"
    @property
    def content(self):
        template = load(os.path.join(os.path.dirname(__file__), "mytemplate.txt"))
        return template % "Hello"

class MyCustomGeneratorWithTemplatePackage(ConanFile):
    exports = "mytemplate.txt"
"""
        client = TestClient()
        client.save({CONANFILE: templated_generator, "mytemplate.txt": "Template: %s"})
        client.run("create . gen/0.1@user/stable")

        client.run("install gen/0.1@user/stable -g=MyCustomTemplateGenerator")
        generated = client.load("customfile.gen")
        self.assertEqual(generated, "Template: Hello")

    def test_install_folder(self):
        # https://github.com/conan-io/conan/issues/5568
        templated_generator = textwrap.dedent("""
            from conans import ConanFile
            from conans.model import Generator
            class MyGenerator(Generator):
                @property
                def filename(self):
                    return "customfile.gen"
                @property
                def content(self):
                    return self.conanfile.install_folder

            class MyCustomGenerator(ConanFile):
                pass
            """)
        client = TestClient()
        client.save({CONANFILE: templated_generator, "mytemplate.txt": "Template: %s"})
        client.run("create . gen/0.1@user/stable")
        client.run("install gen/0.1@user/stable -g=MyGenerator")
        generated = client.load("customfile.gen")
        self.assertEqual(generated, client.current_folder)
