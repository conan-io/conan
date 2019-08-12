import textwrap
import unittest

from conans.paths import CONANFILE, CONANFILE_TXT
from conans.test.utils.tools import TestClient


class TestPackageInfo(unittest.TestCase):

    def package_info_called_in_local_cache_test(self):
        client = TestClient()
        conanfile_tmp = '''
from conans import ConanFile
import os

class HelloConan(ConanFile):
    name = "%s"
    version = "1.0"
    build_policy = "missing"
    options = {"switch": ["1",  "0"]}
    default_options = "switch=0"
    %s
    
    def build(self):
        self.output.warn("Env var MYVAR={0}.".format(os.getenv("MYVAR", "")))

    def package_info(self):
        if self.options.switch == "0": 
            self.env_info.MYVAR = "foo"
        else:
            self.env_info.MYVAR = "bar"

'''
        for index in range(4):
            requires = "requires = 'Lib%s/1.0@conan/stable'" % index if index > 0 else ""
            conanfile = conanfile_tmp % ("Lib%s" % (index + 1), requires)
            client.save({CONANFILE: conanfile}, clean_first=True)
            client.run("create . conan/stable")

        txt = "[requires]\nLib4/1.0@conan/stable"
        client.save({CONANFILE_TXT: txt}, clean_first=True)
        client.run("install . -o *:switch=1")
        self.assertIn("Lib1/1.0@conan/stable: WARN: Env var MYVAR=.", client.out)
        self.assertIn("Lib2/1.0@conan/stable: WARN: Env var MYVAR=bar.", client.out)
        self.assertIn("Lib3/1.0@conan/stable: WARN: Env var MYVAR=bar.", client.out)
        self.assertIn("Lib4/1.0@conan/stable: WARN: Env var MYVAR=bar.", client.out)

        client.run("install . -o *:switch=0 --build Lib3")
        self.assertIn("Lib3/1.0@conan/stable: WARN: Env var MYVAR=foo", client.out)

    def package_info_name_test(self):
        dep = textwrap.dedent("""
            import os
            from conans import ConanFile


            class Dep(ConanFile):

                def package_info(self):
                    self.cpp_info.name = "MyCustomGreatName"
                """)
        intermediate = textwrap.dedent("""
            import os
            from conans import ConanFile


            class Intermediate(ConanFile):
                requires = "dep/1.0@us/ch"
                """)
        consumer = textwrap.dedent("""
            from conans import ConanFile


            class Consumer(ConanFile):
                requires = "intermediate/1.0@us/ch"

                def build(self):
                    for dep_key, dep_value in self.deps_cpp_info.dependencies:
                        self.output.info("%s name: %s" % (dep_key, dep_value.name))
                """)

        client = TestClient()
        client.save({"conanfile_dep.py": dep,
                     "conanfile_intermediate.py": intermediate,
                     "conanfile_consumer.py": consumer})
        client.run("create conanfile_dep.py dep/1.0@us/ch")
        client.run("create conanfile_intermediate.py intermediate/1.0@us/ch")
        client.run("create conanfile_consumer.py consumer/1.0@us/ch")
        self.assertIn("intermediate name: intermediate", client.out)
        self.assertIn("dep name: MyCustomGreatName", client.out)
