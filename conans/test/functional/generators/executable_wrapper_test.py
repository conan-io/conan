import unittest
import textwrap

from conans.test.utils.tools import TestClient


class ExecutableWrapperGeneratorTestCase(unittest.TestCase):
    zlib = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "zlib"

            def package_info(self):
                self.cpp_info.filter_empty = False
    """)

    build_requires = textwrap.dedent("""
        import os
        import stat
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "cmake"
            requires = "zlib/1.0"

            def build(self):
                with open("cmake", "w") as f:
                    f.write("set -e\\n")
                    f.write("set -x\\n")
                    f.write("ls -la\\n")
                st = os.stat('cmake')
                os.chmod('cmake', st.st_mode | stat.S_IEXEC)

            def package(self):
                self.copy("cmake", dst="bin")

            def package_info(self):
                self.cpp_info.filter_empty = False
                self.cpp_info.exes = ["cmake"]
                self.env_info.PATH = [os.path.join(self.package_folder, "bin")]
    """)

    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Application(ConanFile):
            name = "app"
            requires = "zlib/1.0"
            build_requires = "cmake/1.0"

            def build(self):
                self.run("cmake")
    """)

    def test_basic(self):
        t = TestClient()
        t.current_folder = '/private/var/folders/fc/6mvcrc952dqcjfhl4c7c11ph0000gn/T/tmpwqp1praeconans/path with spaces'
        t.cache_folder = '/private/var/folders/fc/6mvcrc952dqcjfhl4c7c11ph0000gn/T/tmpib49nmlbconans/path with spaces'
        t.save({'zlib.py': self.zlib,
                'cmake.py': self.build_requires,
                'app.py': self.conanfile})
        t.run("create zlib.py zlib/1.0@ --profile=default")
        t.run("create cmake.py cmake/1.0@ --profile=default")
        t.run("install app.py --profile:host=default --profile:build=default -g virtualenv -g executable_wrapper")
        print(t.out)
        self.fail("AAA")
