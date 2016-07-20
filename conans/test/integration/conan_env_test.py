import unittest
from conans.test.tools import TestClient
from conans.util.files import load
import os
import platform


class ConanEnvTest(unittest.TestCase):

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
