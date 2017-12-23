import unittest
from conans.test.utils.tools import TestClient
from conans.util.files import load
import os


class ConanfileExtendTest(unittest.TestCase):

    def setUp(self):
        client = TestClient()
        base = '''
from conans import ConanFile

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
'''

        files = {"conanfile.py": base}
        client.save(files)
        client.run("export . user/channel")
        base = '''
from conans import ConanFile

class ConanOtherLib(ConanFile):
    name = "otherlib"
    version = "0.2"
    options = {"otherlib_option": [1, 2, 3]}
    default_options="otherlib_option=3"
'''

        files = {"conanfile.py": base}
        client.save(files)
        client.run("export . user/channel")

        self.base_folder = client.base_folder

    def test_base(self):

        base = '''
from conans import ConanFile

class HelloConan2(ConanFile):
    name = "test"
    version = "1.9"
    requires = "lib/0.1@user/channel"
    options = {"test_option": [1, 2, 3]}
    default_options="test_option=2"
    my_flag = False

    def build(self):
        self.output.info("MyFlag %s" % self.my_flag)
    '''
        extension = '''
from conans import ConanFile, CMake
from conanfile import HelloConan2

class DevConanFile(HelloConan2):
    my_flag = True

    def config(self):
        self.options["otherlib"].otherlib_option = 1

    def requirements(self):
        self.requires("otherlib/0.2@user/channel")

    '''
        files = {"conanfile.py": base,
                 "conanfile_dev.py": extension}

        client = TestClient(self.base_folder)
        client.save(files)
        client.run("install . --build")
        conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
        self.assertIn("lib/0.1@user/channel", conaninfo)
        self.assertIn("test_option=2", conaninfo)
        self.assertNotIn("otherlib/0.2@user/channel", conaninfo)
        self.assertNotIn("otherlib:otherlib_option=1", conaninfo)
        client.run("build .")
        self.assertIn("MyFlag False", client.user_io.out)
        client.run("info .")
        self.assertIn("lib/0.1@user/channel", client.user_io.out)
        self.assertNotIn("otherlib/0.2@user/channel", client.user_io.out)

        client.run("install conanfile_dev.py --build")
        conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
        self.assertIn("lib/0.1@user/channel", conaninfo)
        self.assertIn("test_option=2", conaninfo)
        self.assertIn("otherlib/0.2@user/channel", conaninfo)
        self.assertIn("otherlib:otherlib_option=1", conaninfo)
        client.run("build ./conanfile_dev.py")
        self.assertIn("MyFlag True", client.user_io.out)
        client.run("info conanfile_dev.py")
        self.assertIn("lib/0.1@user/channel", client.user_io.out)
        self.assertIn("otherlib/0.2@user/channel", client.user_io.out)

    def test_txt(self):
        base = '''[requires]
lib/0.1@user/channel
'''
        extension = '''[requires]
lib/0.1@user/channel
otherlib/0.2@user/channel

[options]
otherlib:otherlib_option = 1
'''
        files = {"conanfile.txt": base,
                 "conanfile_dev.txt": extension}

        client = TestClient(self.base_folder)
        client.save(files)
        client.run("install . --build")
        conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
        self.assertIn("lib/0.1@user/channel", conaninfo)
        self.assertNotIn("otherlib/0.2@user/channel", conaninfo)
        self.assertNotIn("otherlib:otherlib_option=1", conaninfo)

        client.run("install conanfile_dev.txt --build")
        conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
        self.assertIn("lib/0.1@user/channel", conaninfo)
        self.assertIn("otherlib/0.2@user/channel", conaninfo)
        self.assertIn("otherlib:otherlib_option=1", conaninfo)
