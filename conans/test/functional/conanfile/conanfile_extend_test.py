import unittest

from conans.test.utils.tools import TestClient


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

        self.cache_folder = client.cache_folder

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

        # Do not adjust cpu_count, it is reusing a cache
        client = TestClient(self.cache_folder, cpu_count=False)
        client.save(files)
        client.run("install . --build")
        conaninfo = client.load("conaninfo.txt")
        self.assertIn("lib/0.1@user/channel", conaninfo)
        self.assertIn("test_option=2", conaninfo)
        self.assertNotIn("otherlib/0.2@user/channel", conaninfo)
        self.assertNotIn("otherlib:otherlib_option=1", conaninfo)
        client.run("build .")
        self.assertIn("MyFlag False", client.out)
        client.run("info .")
        self.assertIn("lib/0.1@user/channel", client.out)
        self.assertNotIn("otherlib/0.2@user/channel", client.out)

        client.run("install conanfile_dev.py --build")
        conaninfo = client.load("conaninfo.txt")
        self.assertIn("lib/0.1@user/channel", conaninfo)
        self.assertIn("test_option=2", conaninfo)
        self.assertIn("otherlib/0.2@user/channel", conaninfo)
        self.assertIn("otherlib:otherlib_option=1", conaninfo)
        client.run("build ./conanfile_dev.py")
        self.assertIn("MyFlag True", client.out)
        client.run("info conanfile_dev.py")
        self.assertIn("lib/0.1@user/channel", client.out)
        self.assertIn("otherlib/0.2@user/channel", client.out)

    def test_conanfile_subclass(self):
        base = '''
from conans import ConanFile

class ConanBase(ConanFile):
    requires = "lib/0.1@user/channel"
    options = {"test_option": [1, 2, 3]}
    default_options="test_option=2"
    my_flag = False

    def build(self):
        self.output.info("build() MyFlag: %s" % self.my_flag)
    '''
        extension = '''
from base_conan import ConanBase

class ConanFileToolsTest(ConanBase):
    name = "test"
    version = "1.9"
    exports = "base_conan.py"

    def config(self):
        self.options["otherlib"].otherlib_option = 1

    def requirements(self):
        self.requires("otherlib/0.2@user/channel")

    def source(self):
        self.output.info("source() my_flag: %s" % self.my_flag)
    '''
        files = {"base_conan.py": base,
                 "conanfile.py": extension}
        # Do not adjust cpu_count, it is reusing a cache
        client = TestClient(self.cache_folder, cpu_count=False)

        client.save(files)
        client.run("create . conan/testing -o test:test_option=3 --build")
        self.assertIn("lib/0.1@user/channel from local cache", client.out)
        self.assertIn("test/1.9@conan/testing: source() my_flag: False", client.out)
        self.assertIn("test/1.9@conan/testing: build() MyFlag: False", client.out)
        client.run("install . -o test:test_option=3")
        conaninfo = client.load("conaninfo.txt")
        self.assertIn("lib/0.1@user/channel", conaninfo)
        self.assertIn("test_option=3", conaninfo)
        self.assertIn("otherlib/0.2@user/channel", conaninfo)
        self.assertIn("otherlib:otherlib_option=1", conaninfo)

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

        # Do not adjust cpu_count, it is reusing a cache
        client = TestClient(self.cache_folder, cpu_count=False)
        client.save(files)
        client.run("install . --build")
        conaninfo = client.load("conaninfo.txt")
        self.assertIn("lib/0.1@user/channel", conaninfo)
        self.assertNotIn("otherlib/0.2@user/channel", conaninfo)
        self.assertNotIn("otherlib:otherlib_option=1", conaninfo)

        client.run("install conanfile_dev.txt --build")
        conaninfo = client.load("conaninfo.txt")
        self.assertIn("lib/0.1@user/channel", conaninfo)
        self.assertIn("otherlib/0.2@user/channel", conaninfo)
        self.assertIn("otherlib:otherlib_option=1", conaninfo)
