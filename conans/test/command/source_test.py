import unittest

from conans.client import tools
from conans.paths import CONANFILE, BUILD_INFO
from conans.test.utils.tools import TestClient
from conans.util.files import load, mkdir
import os


class SourceTest(unittest.TestCase):

    def source_local_cwd_test(self):
        conanfile = '''
import os
from conans import ConanFile

class ConanLib(ConanFile):
    name = "Hello"
    version = "0.1"

    def source(self):
        self.output.info("Running source!")
        self.output.info("cwd=>%s" % os.getcwd())
'''
        client = TestClient()
        client.save({CONANFILE: conanfile})
        subdir = os.path.join(client.current_folder, "subdir")
        os.mkdir(subdir)
        client.run("install .. --cwd subdir")  # IMPORTANT! SHOULD WE CHANGE THE CWD FROM INSTALL TO BUILD_FOLDER?
        client.run("source . --build_folder subdir --source_folder subdir")
        self.assertIn("PROJECT: Configuring sources", client.user_io.out)
        self.assertIn("PROJECT: cwd=>%s" % subdir, client.user_io.out)

    def local_source_src_not_exist_test(self):
        conanfile = '''
import os
from conans import ConanFile

class ConanLib(ConanFile):
    name = "Hello"
    version = "0.1"

    def source(self):
        pass
'''
        client = TestClient()
        client.save({CONANFILE: conanfile})
        # Automatically created
        client.run("source . --source_folder=src")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "src")))

    def build_folder_no_exists_crash_test(self):
        conanfile = '''
import os
from conans import ConanFile

class ConanLib(ConanFile):
    name = "Hello"
    version = "0.1"

    def source(self):
        pass
'''
        client = TestClient()
        client.save({CONANFILE: conanfile})
        # Automatically created
        error = client.run("source . --build_folder=missing_folder", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Specified build_folder doesn't exist", client.out)

    def build_folder_reading_infos_test(self):
        conanfile = '''
import os
from conans import ConanFile

class ConanLib(ConanFile):
    name = "Hello"
    version = "0.1"

    def package_info(self):
        self.cpp_info.cppflags.append("FLAG")
        self.env_info.MYVAR = "foo"
        self.user_info.OTHERVAR = "bar"
'''
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export conan/testing")

        conanfile = '''
import os
from conans import ConanFile
from conans.util.files import save

class ConanLib(ConanFile):

    requires="Hello/0.1@conan/testing"

    def source(self):
        self.output.info("FLAG=%s" % self.deps_cpp_info["Hello"].cppflags[0])
        self.output.info("MYVAR=%s" % self.deps_env_info["Hello"].MYVAR)
        self.output.info("OTHERVAR=%s" % self.deps_user_info["Hello"].OTHERVAR)
        self.output.info("CURDIR=%s" % os.getcwd())
        
'''
        # First, failing source()
        client.save({CONANFILE: conanfile}, clean_first=True)
        build_folder = os.path.join(client.current_folder, "build")
        src_folder = os.path.join(client.current_folder, "src")
        mkdir(build_folder)
        mkdir(src_folder)
        client.run("source . --build_folder='%s' --source_folder='%s'" % (build_folder, src_folder),
                   ignore_error=True)
        self.assertIn("self.deps_cpp_info not defined.", client.out)

        client.run("install .. --cwd build --build ")  # IMPORTANT! change cwd with build_folder?
        client.run("source . --build_folder='%s' --source_folder='%s'" % (build_folder, src_folder),
                   ignore_error=True)
        self.assertIn("FLAG=FLAG", client.out)
        self.assertIn("MYVAR=foo", client.out)
        self.assertIn("OTHERVAR=bar", client.out)
        self.assertIn("CURDIR=%s" % src_folder, client.out)

    def local_source_test(self):
        conanfile = '''
from conans import ConanFile
from conans.util.files import save

class ConanLib(ConanFile):

    def source(self):
        self.output.info("Running source!")
        err
        save("file1.txt", "Hello World")
'''
        # First, failing source()
        client = TestClient()
        client.save({CONANFILE: conanfile,
                     BUILD_INFO: ""})

        client.run("source .", ignore_error=True)
        self.assertIn("PROJECT: Running source!", client.user_io.out)
        self.assertIn("ERROR: PROJECT: Error in source() method, line 9", client.user_io.out)

        # Fix the error and repeat
        client.save({CONANFILE: conanfile.replace("err", "")})
        client.run("source .")
        self.assertIn("PROJECT: Configuring sources in", client.user_io.out)
        self.assertIn("PROJECT: Running source!", client.user_io.out)
        self.assertEqual("Hello World", load(os.path.join(client.current_folder, "file1.txt")))
