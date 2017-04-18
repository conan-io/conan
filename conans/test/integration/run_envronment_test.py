import unittest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files


class RunEnvironmentTest(unittest.TestCase):

    def test_run_environment(self):
        client = TestClient()
        files = cpp_hello_conan_files("Hello0", "0.1")
        files[CONANFILE] = files[CONANFILE].replace('self.copy(pattern="*.so", dst="lib", keep_path=False)',
                                                    '''self.copy(pattern="*.so", dst="lib", keep_path=False)
        self.copy(pattern="*say_hello*", dst="bin", keep_path=False)''')
        client.save(files)
        client.run("export lasote/stable")

        reuse = '''
from conans import ConanFile, RunEnvironment, tools

class HelloConan(ConanFile):
    name = "Reuse"
    version = "0.1"
    build_policy = "missing"
    requires = "Hello0/0.1@lasote/stable"

    def build(self):
        run_env = RunEnvironment(self)
        with tools.environment_append(run_env.vars):
            self.run("say_hello")
'''

        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("install --build missing")
        client.run("build")
