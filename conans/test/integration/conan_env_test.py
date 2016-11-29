import unittest
from conans.test.tools import TestClient
from conans.util.files import load
import os
import platform
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.paths import CONANFILE


class ConanEnvTest(unittest.TestCase):

    def dual_compiler_settings_and_env_test(self):

        def patch_conanfile(conanfile):
            return conanfile + '''
    def build(self):
        import os
        self.output.warn("COMPILER: %s=>%s" % (self.name, self.settings.compiler))
        self.output.warn("CXX: %s=>%s" % (self.name, os.environ["CXX"]))
        self.output.warn("CC: %s=>%s" % (self.name, os.environ["CC"]))
'''

        client = TestClient()
        files = cpp_hello_conan_files("Hello0", "1.0", deps=[], build=False)
        files[CONANFILE] = patch_conanfile(files[CONANFILE])
        client.save(files)
        client.run("export lasote/stable")

        files = cpp_hello_conan_files("Hello1", "1.0", 
                                      deps=["Hello0/1.0@lasote/stable"], build=False)
        files[CONANFILE] = patch_conanfile(files[CONANFILE])
        client.save(files)
        client.run("export lasote/stable")

        # Both with same settings
        client.run("install Hello1/1.0@lasote/stable --build -s compiler=gcc"
                   " -s compiler.version=4.6 -s compiler.libcxx=libstdc++11"
                   " -e CXX=/mycompilercxx -e CC=/mycompilercc")

        self.assertIn("COMPILER: Hello0=>gcc", client.user_io.out)
        self.assertIn("CXX: Hello0=>/mycompilercxx", client.user_io.out)
        self.assertIn("CC: Hello0=>/mycompilercc", client.user_io.out)

        self.assertIn("COMPILER: Hello1=>gcc", client.user_io.out)
        self.assertIn("CXX: Hello1=>/mycompilercxx", client.user_io.out)
        self.assertIn("CC: Hello1=>/mycompilercc", client.user_io.out)

        # Different for Hello0
        client.run("install Hello1/1.0@lasote/stable --build -s compiler=gcc"
                   " -s compiler.version=4.6 -s compiler.libcxx=libstdc++11"
                   " -e CXX=/mycompilercxx -e CC=/mycompilercc"
                   " -s Hello0:compiler=clang -s Hello0:compiler.version=3.7"
                   " -s Hello0:compiler.libcxx=libstdc++"
                   " -e Hello0:CXX=/othercompilercxx -e Hello0:CC=/othercompilercc")

        self.assertIn("COMPILER: Hello0=>clang", client.user_io.out)
        self.assertIn("CXX: Hello0=>/othercompilercxx", client.user_io.out)
        self.assertIn("CC: Hello0=>/othercompilercc", client.user_io.out)

        self.assertIn("COMPILER: Hello1=>gcc", client.user_io.out)
        self.assertIn("CXX: Hello1=>/mycompilercxx", client.user_io.out)
        self.assertIn("CC: Hello1=>/mycompilercc", client.user_io.out)

    def conan_env_deps_test(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    def package_info(self):
        self.env_info.var1="bad value"
        self.env_info.var2.append("value2")
        self.env_info.var3="Another value"
        self.env_info.path = "/dir"
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
        self.requires("Hello/0.1@lasote/stable")

    def package_info(self):
        self.env_info.var1="good value"
        self.env_info.var2.append("value3")
    '''
        files["conanfile.py"] = conanfile
        client.save(files, clean_first=True)
        client.run("export lasote/stable")
        client.run("install Hello2/0.1@lasote/stable --build -g virtualenv")
        ext = "bat" if platform.system() == "Windows" else "sh"
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "activate.%s" % ext)))
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "deactivate.%s" % ext)))
        activate_contents = load(os.path.join(client.current_folder, "activate.%s" % ext))
        deactivate_contents = load(os.path.join(client.current_folder, "deactivate.%s" % ext))
        self.assertNotIn("bad value", activate_contents)
        self.assertIn("var1=good value", activate_contents)
        if platform.system() == "Windows":
            self.assertIn("var2=value3;value2;%var2%", activate_contents)
        else:
            self.assertIn("var2=value3:value2:$var2", activate_contents)
        self.assertIn("Another value", activate_contents)
        self.assertIn("PATH=/dir", activate_contents)

        self.assertIn('var1=', deactivate_contents)
        self.assertIn('var2=', deactivate_contents)
