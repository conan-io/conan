import unittest
from conans.errors import ConanException
from conans.paths import CONANFILE, BUILD_INFO
from conans.test.utils.tools import TestClient
from conans.util.files import load, mkdir
import os


class SourceTest(unittest.TestCase):

    def source_reference_test(self):
        client = TestClient()
        error = client.run("source lib/1.0@conan/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("'conan source' doesn't accept a reference anymore", client.out)

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
        client.run("install . --install-folder subdir")
        client.run("source . --install-folder subdir --source_folder subdir")
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
        error = client.run("source . --install-folder=missing_folder", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Specified info-folder doesn't exist", client.out)

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
        assert(os.getcwd() == self.source_folder)
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
        client.run("source . --install-folder='%s' --source_folder='%s'" % (build_folder, src_folder),
                   ignore_error=True)
        self.assertIn("self.deps_cpp_info not defined.", client.out)

        client.run("install . --install-folder build --build ")
        client.run("source . --install-folder='%s' --source_folder='%s'" % (build_folder, src_folder),
                   ignore_error=True)
        self.assertIn("FLAG=FLAG", client.out)
        self.assertIn("MYVAR=foo", client.out)
        self.assertIn("OTHERVAR=bar", client.out)
        self.assertIn("CURDIR=%s" % src_folder, client.out)

    def repeat_args_fails_test(self):
        conanfile = '''
from conans import ConanFile
class ConanLib(ConanFile):

    def source(self):
        pass
'''
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("source . --source-folder sf")
        with self.assertRaisesRegexp(Exception, "Command failed"):
            client.run("source . --source-folder sf --source-folder sf")
        with self.assertRaisesRegexp(Exception, "Command failed"):
            client.run("source . --source-folder sf --install-folder if --install-folder rr")

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
